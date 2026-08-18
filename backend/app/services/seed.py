import uuid
from pathlib import Path

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Company, TzTemplate, TzTemplateBlock, TzTemplateStage
from app.services import xlsx_parser
from app.services.docx_parser import build_blocks_schema, new_template_docx_key, parse_docx_template
from app.services.minio_client import get_minio_service

settings = get_settings()

XLSX_FILE_MAP = [
    ("0. Компании.xlsx", xlsx_parser.ingest_companies),
    ("1. Договоры.xlsx", xlsx_parser.ingest_contracts),
]


async def seed_xlsx(db: AsyncSession) -> None:
    count = (await db.execute(select(func.count()).select_from(Company))).scalar_one()
    if count > 0:
        logger.info("Справочники уже засеяны, пропускаю xlsx-сидирование")
        return

    xlsx_dir = Path(settings.seed_xlsx_dir)
    if not xlsx_dir.exists():
        logger.warning(f"Каталог {xlsx_dir} не найден, пропускаю xlsx-сидирование")
        return

    for filename, handler in XLSX_FILE_MAP:
        path = xlsx_dir / filename
        if path.exists():
            data = path.read_bytes()
            result = await handler(db, data)
            logger.info(f"Загружен {filename}: {result}")

    products_path = xlsx_dir / "3. Договор + продукты.xlsx"
    rates_path = xlsx_dir / "4. Продукты + расценки.xlsx"
    if products_path.exists():
        result = await xlsx_parser.ingest_products_rates(
            db, products_path.read_bytes(), rates_path.read_bytes() if rates_path.exists() else None
        )
        logger.info(f"Загружены продукты/расценки: {result}")

    operations_path = xlsx_dir / "5. Продукты + Операции.xlsx"
    if operations_path.exists():
        result = await xlsx_parser.ingest_operations(db, operations_path.read_bytes())
        logger.info(f"Загружены операции: {result}")

    calc_path = xlsx_dir / "2. Договор + РС.xlsx"
    if calc_path.exists():
        result = await xlsx_parser.ingest_calculations(db, calc_path.read_bytes())
        logger.info(f"Загружены РС: {result}")


TEMPLATE_FILES = [
    ("concept_geology", "Концепт геологии", "ТЗ Концепт геологии.docx"),
    ("concept_facilities", "Концепт обустройства", "ТЗ Концепт обустройства.docx"),
    ("concept_completion", "Интегрированный концепт заканчивания", "ТЗ Интегрированный концепт заканчивания.docx"),
    ("concept_development", "Интегрированный концепт развития", "ТЗ Интегрированный концепт развития.docx"),
    ("engineering_support", "Сопровождение инженерных работ и высокорисковых операций", "ТЗ Сопровождение инженерных работ и высокорисковых операций.docx"),
    ("ptd_nng", "Приложение 1. ТЗ (шаблон ПТД ННГ)_2026", "Приложение 1. ТЗ (шаблон ПТД ННГ)_2026.docx"),
    ("ptd_do", "Приложение 1. ТЗ (шаблон ПТД ДО)_2026", "Приложение 1. ТЗ (шаблон ПТД ДО)_2026.docx"),
    ("pz_new_field", "Приложение 1. ТЗ (ПЗ Нового м-я)", "Приложение 1. ТЗ (ПЗ Нового м-я).docx"),
    ("ptd_opz_uvs", "Приложение 3. ТЗ ПТД_ОПЗ УВС Песц НГКМ", "Приложение 3. ТЗ ПТД_ОПЗ УВС Песц НГКМ.docx"),
    ("ptd_default", "Прил 1_ТЗ_ПТД", "Прил 1_ТЗ_ПТД.docx"),
    ("form_2_1", "Приложение № 2.1 Форма Технического задания", "Приложение № 2.1 Форма Технического задания.docx"),
]


async def seed_tz_templates(db: AsyncSession) -> None:
    count = (await db.execute(select(func.count()).select_from(TzTemplate))).scalar_one()
    if count > 0:
        logger.info("Шаблоны ТЗ уже засеяны, пропускаю docx-сидирование")
        return

    templates_dir = Path(settings.seed_tz_templates_dir)
    minio = get_minio_service()

    for code, name, filename in TEMPLATE_FILES:
        path = templates_dir / filename
        if path.exists():
            file_bytes = path.read_bytes()
            parsed = parse_docx_template(file_bytes)
        else:
            logger.warning(f"Шаблон {filename} не найден в {templates_dir}, использую дефолтную структуру")
            from app.services.docx_parser import ParsedTemplate, _default_blocks

            parsed = ParsedTemplate(blocks=_default_blocks(), stages=[], raw_docx=b"")

        template_id = uuid.uuid4()
        docx_key = new_template_docx_key(template_id)
        if parsed.raw_docx:
            try:
                minio.upload_bytes(
                    settings.minio_bucket_templates,
                    docx_key,
                    parsed.raw_docx,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"MinIO недоступен при сидировании шаблона {code}: {exc}")

        template = TzTemplate(
            id=template_id,
            code=code,
            name=name,
            description=f"Шаблон ТЗ «{name}»",
            minio_docx_key=docx_key,
            blocks_schema=build_blocks_schema(parsed.blocks),
        )
        db.add(template)
        await db.flush()

        for block in parsed.blocks:
            db.add(
                TzTemplateBlock(
                    template_id=template.id,
                    block_code=block.code,
                    block_name=block.name,
                    block_order=block.order,
                    json_schema={"fields": block.fields, "is_stages_block": block.is_stages_block},
                )
            )

        for stage in parsed.stages:
            db.add(
                TzTemplateStage(
                    template_id=template.id,
                    stage_order=stage["stage_order"],
                    stage_name=stage["stage_name"],
                    default_requirements=stage.get("default_requirements"),
                    default_results=stage.get("default_results"),
                )
            )

    await db.commit()
    logger.info("Сидирование шаблонов ТЗ завершено")


PACKAGE_TEMPLATE_FILES = [
    ("Наряд-заказ_ПЗ.docx", "package/naryad_zakaz.docx"),
    ("Приложение 1. ТЗ.docx", "package/tz_appendix1.docx"),
    ("Приложение № 2.1 Форма Технического задания.docx", "package/tz_form_2_1.docx"),
    ("Приложение 2. КП.xlsx", "package/kp.xlsx"),
    ("Приложение 3. РС.xlsx", "package/rs.xlsx"),
]

_PACKAGE_CONTENT_TYPES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


async def seed_package_templates() -> None:
    """Загружает исходные файлы комплекта документов (seed/package) в MinIO,
    если они там ещё отсутствуют. Идемпотентно — проверяет каждый файл отдельно."""
    package_dir = Path(settings.seed_package_dir)
    if not package_dir.exists():
        logger.warning(f"Каталог {package_dir} не найден, пропускаю сидирование комплекта документов")
        return

    try:
        minio = get_minio_service()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"MinIO недоступен, пропускаю сидирование комплекта документов: {exc}")
        return

    for filename, minio_key in PACKAGE_TEMPLATE_FILES:
        path = package_dir / filename
        if not path.exists():
            logger.warning(f"Файл шаблона {filename} не найден в {package_dir}")
            continue
        try:
            if minio.object_exists(settings.minio_bucket_templates, minio_key):
                continue
            ext = minio_key.rsplit(".", 1)[-1]
            minio.upload_bytes(
                settings.minio_bucket_templates,
                minio_key,
                path.read_bytes(),
                _PACKAGE_CONTENT_TYPES.get(ext, "application/octet-stream"),
            )
            logger.info(f"Загружен шаблон комплекта документов {filename} -> {minio_key}")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"MinIO недоступен при сидировании шаблона {filename}: {exc}")


async def seed_embeddings(db: AsyncSession) -> None:
    """Строит эмбеддинги для семантического поиска (§4.3 SPEC).

    Без этого чат-агент не может предлагать продукты/исполнителей/шаблоны.
    Идемпотентно: пропускается, если эмбеддинги данного типа уже есть.
    """
    from sqlalchemy import func as sa_func

    from app.db.models import Embedding, Product
    from app.services.embeddings import upsert_embedding

    async def _count(entity_type: str) -> int:
        return (
            await db.execute(
                select(sa_func.count()).select_from(Embedding).where(Embedding.entity_type == entity_type)
            )
        ).scalar_one()

    try:
        if await _count("product") == 0:
            products = (await db.execute(select(Product))).scalars().all()
            for p in products:
                await upsert_embedding(db, "product", p.product_id, p.product_name)
            logger.info(f"Построены эмбеддинги продуктов: {len(products)}")

        if await _count("company_services") == 0:
            companies = (await db.execute(select(Company))).scalars().all()
            for c in companies:
                await upsert_embedding(db, "company_services", c.company_id, c.services or c.name)
            logger.info(f"Построены эмбеддинги исполнителей: {len(companies)}")

        if await _count("tz_template") == 0:
            templates = (await db.execute(select(TzTemplate))).scalars().all()
            for t in templates:
                await upsert_embedding(db, "tz_template", str(t.id), f"{t.name} {t.description or ''}")
            logger.info(f"Построены эмбеддинги шаблонов ТЗ: {len(templates)}")
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Построение эмбеддингов при сидировании завершилось ошибкой: {exc}")


async def run_seed(db: AsyncSession) -> None:
    try:
        get_minio_service().ensure_buckets()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"MinIO недоступен при старте: {exc}")
    await seed_xlsx(db)
    await seed_tz_templates(db)
    await seed_package_templates()
    await seed_embeddings(db)
