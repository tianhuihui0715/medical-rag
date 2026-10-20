"""编排改写、知识库路由、权限过滤、双路融合、父块去重及重排。"""

import json
import math
import re
from typing import Any, cast

from langchain_core.output_parsers import JsonOutputParser
from sqlmodel import Session

from clint.mysql_connection import MySQLConnection, get_mysql_connection
from dao import chunk_dao, knowledge_dao
from dao.vector_dao import VectorDao
from model.file_info import FileInfo
from model.search_info import DirectorySearchRequest, SearchBlock, SearchRequest, SearchResult
from service.config_service import ConfigService
from service.model_service import ModelService


class SearchService:
    """一次请求完成检索；推理与 Milvus 调用均在 SQL 事务外执行。"""
    def __init__(
        self, db: MySQLConnection | None = None, models: ModelService | None = None,
        vectors: VectorDao | None = None,
    ):
        self.db = db if db is not None else get_mysql_connection()
        self.models = models if models is not None else ModelService(self.db)
        self.vectors = vectors
        self.config = ConfigService(self.db)

    def search(self, data: SearchRequest | DirectorySearchRequest, user_id: int) -> SearchResult:
        source_path = None
        if isinstance(data, DirectorySearchRequest):
            department, position = data.department.strip(), data.position.strip()
            if any(not part or part in (".", "..") or "/" in part or "\\" in part
                   for part in (department, position)):
                raise ValueError("部门和职位必须为单层目录名称")
            source_path = f"{department}/{position}/"
            data = SearchRequest(query=data.query, top_k=data.top_k)
        result = SearchResult(query=data.query)
        if not data.query.strip():
            return result
        recall_k = data.recall_k if data.recall_k is not None else int(
            cast(str, self.config.get_value("search_recall_k")),
        )
        top_k = data.top_k if data.top_k is not None else int(
            cast(str, self.config.get_value("search_top_k")),
        )
        if recall_k <= 0 or top_k <= 0:
            raise ValueError("recall_k 和 top_k 必须大于 0")
        if data.sparse_weight is not None and not 0 <= data.sparse_weight <= 1:
            raise ValueError("sparse_weight 必须在 0 到 1 之间")
        with self.db.session() as session:
            allowed = {item.id for item in knowledge_dao.list_accessible(session, user_id, source_path)}
        if data.knowledge_ids is not None:
            allowed.intersection_update(data.knowledge_ids)
        if not allowed:
            return result

        result.questions = self._questions(data.query, self.models.rewrite(data.query))
        # 指定部门和职位时，目录已经限定知识范围，不再让模型选择知识库。
        knowledge_ids = sorted(allowed) if source_path is not None else (
            self.models.select_knowledge(json.dumps({"questions": result.questions}, ensure_ascii=False), user_id)
            if data.knowledge_ids is None else data.knowledge_ids
        )
        result.knowledge_ids = list(dict.fromkeys(kid for kid in knowledge_ids if kid in allowed))
        if not result.knowledge_ids:
            return result
        model = self.models.get_default("embedding")
        if model is None:
            raise LookupError("尚未选择默认向量模型")
        model_id = cast(int, model.id)
        with self.db.session() as session:
            files = self._files(session, user_id, result.knowledge_ids, model_id, source_path)
        if not files:
            return result
        collections: dict[str, list[int]] = {}
        for file_id, file in files.items():
            collections.setdefault(cast(str, file.vector_collection), []).append(file_id)
        embeddings = self.models.call(model_id, "embedding", {"input": result.questions})
        rows = sorted(embeddings.get("data", []), key=lambda row: row["index"])
        if [row["index"] for row in rows] != list(range(len(result.questions))):
            raise RuntimeError("问题向量与输入数量或索引不匹配")
        vectors = self.vectors if self.vectors is not None else VectorDao()
        hits: dict[int, dict[str, Any]] = {}
        for question, row in zip(result.questions, rows):
            if "sparse_embedding" not in row:
                raise RuntimeError("当前向量模型未返回稀疏向量，请选择双向量模型")
            sparse = {int(token): float(weight) for token, weight in row["sparse_embedding"].items()}
            weight = self._sparse_weight(question, data.sparse_weight)
            for collection, file_ids in collections.items():
                for hit in vectors.search(collection, file_ids, row["embedding"], sparse, recall_k, weight):
                    parent_id = int(hit["entity"]["parent_id"])
                    file_id = int(hit["entity"]["file_id"])
                    if file_id not in file_ids:
                        continue
                    parent = hits.setdefault(parent_id, {
                        "file_id": file_id, "score": float(hit["distance"]), "children": [], "questions": [],
                    })
                    parent["score"] = max(parent["score"], float(hit["distance"]))
                    if int(hit["id"]) not in parent["children"]:
                        parent["children"].append(int(hit["id"]))
                    if question not in parent["questions"]:
                        parent["questions"].append(question)
        if not hits:
            return result

        # 回溯前重新读取授权，防止模型推理期间撤权或文件重建后仍送出父块正文。
        with self.db.session() as session:
            current = self._files(session, user_id, result.knowledge_ids, model_id, source_path)
            valid_files = [fid for fid, item in current.items() if fid in files and
                           item.vector_collection == files[fid].vector_collection]
            parents = chunk_dao.list_parents(session, list(hits), valid_files)
        parents = [item for item in parents if hits[cast(int, item.id)]["file_id"] == item.file_id]
        parents.sort(key=lambda item: hits[cast(int, item.id)]["score"], reverse=True)
        if not parents:
            return result
        documents = [
            "\n".join(item.meta.get("section", [])) + "\n\n" + item.content
            if item.meta.get("section") else item.content for item in parents
        ]
        scores = [-math.inf] * len(parents)
        for question in result.questions:
            ranked = self.models.call(None, "rerank", {"query": question, "documents": documents})
            ranking = ranked.get("results", [])
            if sorted(item["index"] for item in ranking) != list(range(len(parents))):
                raise RuntimeError("重排模型返回的文档索引不完整或重复")
            for item in ranking:
                score = float(item["relevance_score"])
                if not math.isfinite(score):
                    raise RuntimeError("重排模型返回了无效分数")
                scores[item["index"]] = max(scores[item["index"]], score)

        # 返回前再次核对范围与父块，过滤评分期间撤权、停用和重切的结果。
        with self.db.session() as session:
            current = self._files(session, user_id, result.knowledge_ids, model_id, source_path)
            valid_files = [fid for fid, item in current.items() if fid in files and
                           item.vector_collection == files[fid].vector_collection]
            valid_parents = {item.id for item in chunk_dao.list_parents(session, list(hits), valid_files)}
        for index in sorted(range(len(parents)), key=lambda index: scores[index], reverse=True):
            parent = parents[index]
            parent_id = cast(int, parent.id)
            if parent_id not in valid_parents:
                continue
            hit = hits[parent_id]
            result.blocks.append(SearchBlock(
                file_id=parent.file_id, file_name=current[parent.file_id].name, parent_id=parent_id,
                content=parent.content, page_start=parent.page_start, page_end=parent.page_end,
                meta={key: value for key, value in parent.meta.items()
                      if key not in ("bucket", "object_name", "parsed_object_name")},
                child_ids=hit["children"], questions=hit["questions"],
                fusion_score=hit["score"], score=scores[index],
            ))
            if len(result.blocks) >= top_k:
                break
        return result

    @staticmethod
    def _files(
        session: Session, user_id: int, knowledge_ids: list[int], model_id: int,
        source_path: str | None = None,
    ) -> dict[int, FileInfo]:
        """只检索目录和权限范围内，与查询模型一致且已完成入库的文件。"""
        return {
            cast(int, item.id): item
            for item in knowledge_dao.list_files(session, user_id, knowledge_ids, source_path)
            if item.embedding_model_id == model_id and item.vector_collection
        }

    def _sparse_weight(self, question: str, override: float | None) -> float:
        if override is not None:
            return override
        # 字母与数字组合的型号、错误码增加词匹配权重；普通年份、金额不触发。
        terms = re.findall(r"[A-Za-z0-9_-]+", question)
        exact = any(re.search(r"[A-Za-z]", term) and re.search(r"\d", term) for term in terms)
        key = "search_exact_sparse_weight" if exact else "search_sparse_weight"
        weight = float(cast(str, self.config.get_value(key)))
        if not 0 <= weight <= 1:
            raise ValueError(f"{key} 必须在 0 到 1 之间")
        return weight

    @staticmethod
    def _questions(original: str, rewritten: str) -> list[str]:
        """兼容文本改写和 questions JSON，解析失败时保留可用问题。"""
        try:
            parsed = JsonOutputParser().parse(rewritten)
        except ValueError:
            return [original if rewritten.lstrip().startswith(("{", "[", "```")) else rewritten.strip() or original]
        if isinstance(parsed, dict) and isinstance(parsed.get("questions"), list):
            questions = list(dict.fromkeys(
                question.strip() for question in parsed["questions"] if isinstance(question, str) and question.strip()
            ))
            return questions or [original]
        return [original]
