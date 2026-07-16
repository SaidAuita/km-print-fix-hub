# scratch/prepare_full_build_titles.py
import os
import re
import datetime

def main():
    build_dir = "Build_full/KM Print Fix Hub"
    if not os.path.exists(build_dir):
        print(f"[!] Build dir {build_dir} not found.")
        return
        
    current_date = datetime.date.today().strftime("%Y-%m-%d")
    full_title = f"KM Print Fix Hub v 1.20 ({current_date})"
    print(f"[*] Updating full version titles to '{full_title}' inside {build_dir}...")

    # 1. Replace in translations.json inside Build_full/KM Print Fix Hub
    trans_path = os.path.join(build_dir, "translations.json")
    if os.path.exists(trans_path):
        with open(trans_path, "r", encoding="utf-8") as f:
            content = f.read()
        new_content = content.replace("KM Print Fix Hub v1.20 Light", full_title)
        with open(trans_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print("  -> translations.json updated.")

    # 2. Replace in web/app.py inside Build_full/KM Print Fix Hub
    app_path = os.path.join(build_dir, "web/app.py")
    if os.path.exists(app_path):
        with open(app_path, "r", encoding="utf-8") as f:
            content = f.read()
        new_content = content.replace("KM Print Fix Hub v1.20 Light", full_title)
        with open(app_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print("  -> web/app.py updated.")

if __name__ == "__main__":
    main()
