"""把一个文件或目录中的企业知识写入 MySQL 和 Milvus。"""

import argparse
import asyncio
from pathlib import Path

from aidahelp.config import get_settings
from aidahelp.integrations.embedding import build_embedding_model
from aidahelp.knowledge.loaders import supported_extensions
from aidahelp.persistence.database import Database
from aidahelp.persistence.vector_store import MilvusVectorStore
from aidahelp.services.knowledge_ingestion_service import KnowledgeIngestionService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AidaHelp 知识入库")
    parser.add_argument("path", help="知识文件或目录")
    parser.add_argument("--version", default="v1", help="知识版本")
    parser.add_argument("--category", default=None, help="分类元数据")
    return parser.parse_args()


def discover_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    extensions = supported_extensions()
    return sorted(file for file in path.rglob("*") if file.suffix.lower() in extensions)


async def main() -> None:
    args = parse_args()
    settings = get_settings()
    database = Database(settings)
    embedding = build_embedding_model(settings)
    token = settings.milvus_token.get_secret_value() if settings.milvus_token else None
    vector_store = MilvusVectorStore(
        uri=settings.milvus_uri,
        token=token,
        collection=settings.milvus_collection,
        dimension=embedding.dimension,
    )
    try:
        files = discover_files(Path(args.path).expanduser().resolve())
        if not files:
            raise RuntimeError("没有找到支持的知识文件")
        async with database.session() as session:
            service = KnowledgeIngestionService(
                session=session,
                embedding=embedding,
                vector_store=vector_store,
                settings=settings,
            )
            for file in files:
                result = await service.ingest_file(
                    file,
                    version=args.version,
                    category=args.category,
                )
                print(
                    f"[{result.status}] {file.name}: document={result.document_id}, "
                    f"chunks={result.chunk_count}, reused={result.reused}"
                )
    finally:
        await vector_store.close()
        await embedding.close()
        await database.dispose()


if __name__ == "__main__":
    asyncio.run(main())
