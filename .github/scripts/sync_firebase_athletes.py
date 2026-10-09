import json
import os
import re
import sys
from urllib.request import Request, urlopen

MINIMUM_EXPECTED_ATHLETES = 51
INDEX_FILE = "index.html"
ARRAY_PATTERN = re.compile(
    r"(?ms)^    let baseDadosAtletas = \[.*?^    \];"
)


def js_string(value):
    return (
        json.dumps(value, ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def main():
    endpoint = os.environ["FIREBASE_DATABASE_URL"]
    request = Request(endpoint, headers={"Accept": "application/json"})
    with urlopen(request, timeout=30) as response:
        remote = json.loads(response.read().decode("utf-8"))

    if remote is None:
        print("Firebase ainda não tem a lista base; não há nada para sincronizar.")
        return 0

    athletes = remote if isinstance(remote, list) else list(remote.values())
    clean = []
    seen_names = set()

    for athlete in athletes:
        if not isinstance(athlete, dict):
            continue
        name = athlete.get("nome")
        birth_date = athlete.get("data")
        athlete_id = athlete.get("id")
        if not isinstance(name, str) or not name.strip():
            continue
        if not isinstance(birth_date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", birth_date):
            continue
        if isinstance(athlete_id, bool) or not str(athlete_id).isdigit():
            continue

        name = name.strip()
        name_key = name.casefold()
        if name_key in seen_names:
            raise ValueError(f"Nome de atleta duplicado na base: {name}")
        seen_names.add(name_key)
        clean.append({"id": int(athlete_id), "nome": name, "data": birth_date})

    if len(clean) < MINIMUM_EXPECTED_ATHLETES:
        raise ValueError(
            f"A base Firebase tem apenas {len(clean)} atletas válidos; "
            f"esperavam-se pelo menos {MINIMUM_EXPECTED_ATHLETES}. "
            "O ficheiro index.html não foi alterado."
        )

    clean.sort(key=lambda athlete: (athlete["id"], athlete["nome"].casefold()))
    generated = ["    let baseDadosAtletas = ["]
    for index, athlete in enumerate(clean):
        comma = "," if index < len(clean) - 1 else ""
        generated.append(
            "        { id: "
            + str(athlete["id"])
            + ", nome: "
            + js_string(athlete["nome"])
            + ", data: "
            + js_string(athlete["data"])
            + " }"
            + comma
        )
    generated.append("    ];")
    replacement = "\n".join(generated)

    with open(INDEX_FILE, "r", encoding="utf-8", newline="") as file:
        source = file.read()
    match = ARRAY_PATTERN.search(source)
    if not match:
        raise ValueError("Não foi possível localizar a lista base no index.html.")

    if match.group(0).replace("\r\n", "\n") == replacement:
        print("A lista de atletas já está sincronizada com o Firebase.")
        return 0

    ending = "\r\n" if "\r\n" in source else "\n"
    replacement = replacement.replace("\n", ending)
    updated = source[: match.start()] + replacement + source[match.end() :]
    with open(INDEX_FILE, "w", encoding="utf-8", newline="") as file:
        file.write(updated)

    print(f"Lista base atualizada com {len(clean)} atletas.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"Erro na sincronização: {error}", file=sys.stderr)
        sys.exit(1)
