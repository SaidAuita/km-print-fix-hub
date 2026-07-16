# scratch/prepare_light_build_titles.py
import os
import re

def main():
    build_dir = "Build/KM Print Fix Hub"
    if not os.path.exists(build_dir):
        print(f"[!] Build dir {build_dir} not found.")
        return
        
    # 1. Replace in translations.json inside Build/KM Print Fix Hub
    trans_path = os.path.join(build_dir, "translations.json")
    if os.path.exists(trans_path):
        with open(trans_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Replace '"title": "KM Print Fix Hub v 1.20 (...)"' or similar with '"title": "KM Print Fix Hub v1.20 Light"'
        new_content = re.sub(
            r'"title": "KM Print Fix Hub v\s*1\.\d+ \(\d{4}-\d{2}-\d{2}\)"',
            '"title": "KM Print Fix Hub v1.20 Light"',
            content
        )
        with open(trans_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print("[*] Light translations.json title updated to v1.20 Light")

    # 2. Replace in web/app.py inside Build/KM Print Fix Hub
    app_path = os.path.join(build_dir, "web/app.py")
    if os.path.exists(app_path):
        with open(app_path, "r", encoding="utf-8") as f:
            content = f.read()
        new_content = re.sub(
            r'FastAPI\(title="KM Print Fix Hub v\s*1\.\d+ \(\d{4}-\d{2}-\d{2}\)"\)',
            'FastAPI(title="KM Print Fix Hub v1.20 Light")',
            content
        )
        with open(app_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print("[*] Light web/app.py title updated to v1.20 Light")

if __name__ == "__main__":
    main()
