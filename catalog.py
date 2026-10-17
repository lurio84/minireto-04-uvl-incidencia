"""Lógica mínima del catálogo UVL.

No pretende implementar UVL completo. Los modelos del ejercicio usan un
subconjunto muy pequeño y predecible para que el foco esté en las prácticas de
ingeniería, no en construir un parser.
"""

from __future__ import annotations

import csv
import html
import os
import shutil
import subprocess
from pathlib import Path

REQUIRED_FIELDS = ("id", "title", "author", "description", "file")
UVL_KEYWORDS = {
    "features",
    "constraints",
    "mandatory",
    "optional",
    "alternative",
    "or",
}


def get_catalog_path() -> Path:
    return Path(os.environ.get("CATALOG_FILE", "catalog.csv"))


def get_models_dir() -> Path:
    return Path(os.environ.get("UVL_MODELS_DIR", "models"))


def read_catalog(catalog_path: Path | None = None) -> list[dict[str, str]]:
    path = catalog_path or get_catalog_path()
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def count_features(model_path: Path) -> int:
    """Cuenta características en el pequeño subconjunto UVL del ejercicio."""
    in_features = False
    count = 0

    for raw_line in model_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("//"):
            continue
        if line == "features":
            in_features = True
            continue
        if line == "constraints":
            break
        if not in_features or line in UVL_KEYWORDS:
            continue
        count += 1

    if count == 0:
        raise ValueError(f"{model_path} no contiene características reconocibles")
    return count


def classify_model_size(feature_count: int) -> str:
    if feature_count < 1:
        raise ValueError("feature_count debe ser positivo")
    if feature_count <= 5:
        return "tiny"
    if feature_count <= 15:
        return "small"
    if feature_count <= 30:
        return "medium"
    return "large"


def validate_catalog(
    catalog_path: Path | None = None,
    models_dir: Path | None = None,
) -> list[str]:
    catalog_path = catalog_path or get_catalog_path()
    models_dir = models_dir or get_models_dir()
    errors: list[str] = []

    try:
        rows = read_catalog(catalog_path)
    except (FileNotFoundError, OSError) as exc:
        return [f"No se puede leer el catálogo: {exc}"]

    seen_ids: set[str] = set()
    for line_number, row in enumerate(rows, start=2):
        for field in REQUIRED_FIELDS:
            if not (row.get(field) or "").strip():
                errors.append(f"Línea {line_number}: falta el campo {field}")

        model_id = (row.get("id") or "").strip()
        if model_id in seen_ids:
            errors.append(f"Línea {line_number}: id duplicado {model_id}")
        seen_ids.add(model_id)

        filename = (row.get("file") or "").strip()
        if not filename:
            continue
        model_path = models_dir / filename
        if not model_path.exists():
            errors.append(f"Línea {line_number}: no existe {model_path}")
            continue
        try:
            count_features(model_path)
        except ValueError as exc:
            errors.append(f"Línea {line_number}: {exc}")

    return errors


def build_site(output_dir: Path, generate_diagrams: bool = False) -> None:
    catalog_path = get_catalog_path()
    models_dir = get_models_dir()
    errors = validate_catalog(catalog_path, models_dir)
    if errors:
        raise ValueError("\n".join(errors))

    rows = read_catalog(catalog_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile("style.css", output_dir / "style.css")

    table_rows: list[str] = []
    for row in rows:
        model_path = models_dir / row["file"]
        feature_count = count_features(model_path)
        size = classify_model_size(feature_count)
        diagram = ""
        if generate_diagrams:
            diagram_name = f"{row['id']}.svg"
            _create_diagram(row["title"], feature_count, output_dir / diagram_name)
            diagram = f'<br><img src="{html.escape(diagram_name)}" alt="Diagrama">'

        table_rows.append(
            "<tr>"
            f"<td>{html.escape(row['title'])}{diagram}</td>"
            f"<td>{html.escape(row['author'])}</td>"
            f"<td>{html.escape(row['description'])}</td>"
            f"<td>{feature_count}</td>"
            f"<td>{size}</td>"
            "</tr>"
        )

    document = f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Catálogo UVL</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <h1>Catálogo de modelos UVL</h1>
  <table>
    <thead><tr><th>Modelo</th><th>Autoría</th><th>Descripción</th><th>Características</th><th>Tamaño</th></tr></thead>
    <tbody>{''.join(table_rows)}</tbody>
  </table>
</body>
</html>
"""
    (output_dir / "index.html").write_text(document, encoding="utf-8")


def _create_diagram(title: str, feature_count: int, output_path: Path) -> None:
    dot_source = (
        "digraph model {\n"
        "  node [shape=box];\n"
        f'  model [label="{title}\\n{feature_count} features"];\n'
        "}\n"
    )
    subprocess.run(
        ["dot", "-Tsvg", "-o", str(output_path)],
        input=dot_source,
        text=True,
        check=True,
    )
