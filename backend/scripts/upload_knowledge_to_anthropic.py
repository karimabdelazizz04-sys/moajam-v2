import anthropic
import os
import json

# Resolve everything relative to this script so it runs from any working dir.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
KNOWLEDGE_DIR = os.path.join(BACKEND_DIR, "knowledge")
ENV_PATH = os.path.join(BACKEND_DIR, ".env")


def _load_api_key() -> str:
    """Use ANTHROPIC_API_KEY from the environment, else read it from backend/.env
    (the same file the app loads via pydantic-settings)."""
    key = os.getenv("ANTHROPIC_API_KEY")
    if key:
        return key
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, encoding="utf-8") as env_file:
            for line in env_file:
                line = line.strip()
                if line.startswith("ANTHROPIC_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit(
        "ANTHROPIC_API_KEY not set in the environment or backend/.env"
    )


client = anthropic.Anthropic(api_key=_load_api_key())

FILES_TO_UPLOAD = [
    "A_Banking_Financial.pdf",
    "B_Shipping_Customs_Logistics.pdf",
    "C_Corporate_Commercial.pdf",
    "D_POA_Legal_Instruments.pdf",
    "E_Government_Personal.pdf",
    "F_Tenancy_Real_Estate.pdf",
    "G_Correspondence_Evidence.pdf",
    "H_Medical.pdf",
    "I_Translator_Affairs_Internal.pdf",
    "01_ALL_IN_ONE_KNOWLEDGE_MASTER_RULES.txt",
    "STRICT_MATCHING_DOCUMENT_TYPE_LAYOUT_OVERRIDE.txt",
    "UAE_Legal_Translation_Requirements_Checklist_3.pdf",
]

file_ids = {}
for filename in FILES_TO_UPLOAD:
    path = os.path.join(KNOWLEDGE_DIR, filename)
    if not os.path.exists(path):
        print(f"SKIP: {filename}")
        continue

    media_type = "application/pdf" if filename.endswith(".pdf") else "text/plain"
    print(f"Uploading: {filename}...")
    with open(path, "rb") as f:
        response = client.beta.files.upload(
            file=(filename, f, media_type),
            betas=["files-api-2025-04-14"],
        )
    file_ids[filename] = response.id
    print(f"  -> {response.id}")

# Save the IDs to a file
ids_path = os.path.join(KNOWLEDGE_DIR, ".anthropic_file_ids.json")
with open(ids_path, "w") as f:
    json.dump(file_ids, f, indent=2)

print("\nDone! File IDs saved to .anthropic_file_ids.json")
print(json.dumps(file_ids, indent=2))
