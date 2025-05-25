# developer.py

from flask import Blueprint, render_template, session, redirect, url_for, request, flash
import os
import json

# Define the folder for storing user-created pages
PAGES_FOLDER = os.path.join(os.getcwd(), 'pages')
os.makedirs(PAGES_FOLDER, exist_ok=True)

# Register blueprint
developer_bp = Blueprint('developer', __name__)

# ------------------ Routes ------------------

@developer_bp.route('/developer')
def developer_dashboard():
    print('[ROUTE] developer_dashboard')
    if session.get('username') != 'developer':
        flash("Unauthorized access.")
        return redirect(url_for('login'))

    structure_path = os.path.join(PAGES_FOLDER, "page_structure.json")
    page_structure = []

    # Load existing structure
    if os.path.exists(structure_path):
        with open(structure_path) as f:
            page_structure = json.load(f)

    # ✅ Ensure "Ungrouped" exists
    ungrouped = next((g for g in page_structure if g["group"] == "Ungrouped"), None)
    if not ungrouped:
        ungrouped = {"group": "Ungrouped", "pages": []}
        page_structure.append(ungrouped)

    # ✅ Collect all JSON files from pages/ folder (excluding structure itself)
    all_pages_in_folder = {
        f.replace('.json', '')
        for f in os.listdir(PAGES_FOLDER)
        if f.endswith('.json') and f != "page_structure.json"
    }

    # ✅ Collect all pages already referenced in any group
    referenced_pages = set()
    for group in page_structure:
        for page in group["pages"]:
            if isinstance(page, dict):
                referenced_pages.add(page.get("name"))
            else:
                referenced_pages.add(page)

    # ✅ Find orphaned pages (in folder but not in structure)
    missing_pages = sorted(all_pages_in_folder - referenced_pages)
    for page_name in missing_pages:
        ungrouped["pages"].append({"name": page_name, "order": 9999})

    # 🔢 Sort groups (e.g., 1-Supreme first)
    def group_sort_key(group):
        try:
            return int(group["group"].split('-')[0])
        except:
            return 9999
    page_structure.sort(key=group_sort_key)

    # 🔢 Sort pages in each group
    for group in page_structure:
        if isinstance(group["pages"], list):
            # Normalize string pages to dict
            group["pages"] = [
                {"name": p, "order": 9999} if isinstance(p, str) else p
                for p in group["pages"]
            ]
            group["pages"].sort(key=lambda p: p.get("order", 9999))

    # ✅ Save updated structure (with new orphans added)
    with open(structure_path, 'w') as f:
        json.dump(page_structure, f, indent=2)

    return render_template('developer.html', page_structure=page_structure)



@developer_bp.route('/create_page', methods=['POST'])
def create_page():
    print('[ROUTE] create_page')
    if session.get('username') != 'developer':
        return redirect(url_for('login'))

    page_name = request.form.get('page_name', '').strip().replace(' ', '_')
    group_name = request.form.get('group_name', '').strip()
    new_group_name = request.form.get('new_group_name', '').strip()
    if group_name == "_new" and new_group_name:
        group_name = new_group_name

    if not page_name:
        flash("Page name is required.")
        return redirect(url_for('developer.developer_dashboard'))

    if not group_name:
        flash("Group name is required.")
        return redirect(url_for('developer.developer_dashboard'))

    page_path = os.path.join(PAGES_FOLDER, f"{page_name}.json")
    structure_path = os.path.join(PAGES_FOLDER, "page_structure.json")

    # ✅ Create JSON file if not exists
    if not os.path.exists(page_path):
        with open(page_path, 'w') as f:
            json.dump([], f)
        flash(f"Page '{page_name}' created.")
    else:
        flash("Page already exists.")

    # ✅ Update group structure
    if os.path.exists(structure_path):
        with open(structure_path) as f:
            structure = json.load(f)
    else:
        structure = []

    group_found = False
    for group in structure:
        if group["group"] == group_name:
            if page_name not in group["pages"]:
                group["pages"].append(page_name)
            group_found = True
            break

    if not group_found:
        structure.append({"group": group_name, "pages": [page_name]})

    with open(structure_path, 'w') as f:
        json.dump(structure, f, indent=2)

    # ✅ Go straight to edit mode
    return redirect(url_for('edit_page.edit_page', page_name=page_name))


@developer_bp.route('/move_page', methods=['POST'])
def move_page():
    page_name = request.form.get('page_name', '').strip()
    new_group = request.form.get('new_group', '').strip()
    structure_path = os.path.join(PAGES_FOLDER, "page_structure.json")

    if not page_name or not new_group:
        flash("Missing data.")
        return redirect(url_for('developer.developer_dashboard'))

    if not os.path.exists(structure_path):
        flash("Structure file missing.")
        return redirect(url_for('developer.developer_dashboard'))

    with open(structure_path) as f:
        structure = json.load(f)

    # Remove page from all groups (including dict-style)
    for group in structure:
        original_count = len(group["pages"])
        group["pages"] = [
            p for p in group["pages"]
            if (p.get("name") if isinstance(p, dict) else p) != page_name
        ]
        if len(group["pages"]) < original_count:
            print(f"Removed '{page_name}' from group '{group['group']}'")

    # Add to new group (preserve order if possible)
    for group in structure:
        if group["group"] == new_group:
            group["pages"].append({"name": page_name, "order": 9999})
            break
    else:
        # Group didn't exist — create it
        structure.append({
            "group": new_group,
            "pages": [{"name": page_name, "order": 9999}]
        })

    with open(structure_path, 'w') as f:
        json.dump(structure, f, indent=2)

    flash(f"Page '{page_name}' moved to group '{new_group}'.")
    return redirect(url_for('developer.developer_dashboard'))


@developer_bp.route('/update_page_order', methods=['POST'])
def update_page_order():
    page_name = request.form.get("page_name")
    group_name = request.form.get("group_name")
    new_order = int(request.form.get("order", 9999))
    structure_path = os.path.join(PAGES_FOLDER, "page_structure.json")

    if not (page_name and group_name):
        flash("Missing data for order update.")
        return redirect(url_for('developer.developer_dashboard'))

    if os.path.exists(structure_path):
        with open(structure_path) as f:
            structure = json.load(f)

        for group in structure:
            if group["group"] == group_name:
                # Convert to object form if needed
                group["pages"] = [
                    {"name": p["name"], "order": p["order"]} if isinstance(p, dict)
                    else {"name": p, "order": 9999}
                    for p in group["pages"]
                ]
                for page in group["pages"]:
                    if page["name"] == page_name:
                        page["order"] = new_order

        with open(structure_path, 'w') as f:
            json.dump(structure, f, indent=2)

    return redirect(url_for('developer.developer_dashboard'))


@developer_bp.route('/delete_page/<page_name>', methods=['POST'])
def delete_page(page_name):
    print(f"[ROUTE] delete_page: {page_name}")
    if session.get('username') != 'developer':
        flash("Unauthorized.")
        return redirect(url_for('login'))

    # 🔥 Delete the .json file
    file_path = os.path.join(PAGES_FOLDER, f"{page_name}.json")
    if os.path.exists(file_path):
        os.remove(file_path)
        flash(f"Page '{page_name}' deleted.")
    else:
        flash(f"Page '{page_name}' does not exist.")

    # ✅ Update page_structure.json
    structure_path = os.path.join(PAGES_FOLDER, "page_structure.json")
    if os.path.exists(structure_path):
        with open(structure_path) as f:
            structure = json.load(f)

        for group in structure:
            group["pages"] = [
                p for p in group.get("pages", [])
                if (p.get("name") if isinstance(p, dict) else p) != page_name
            ]

        with open(structure_path, 'w') as f:
            json.dump(structure, f, indent=2)

    return redirect(url_for('developer.developer_dashboard'))


@developer_bp.route('/delete_group', methods=['POST'])
def delete_group():
    group_name = request.form.get("group_name", "").strip()
    structure_path = os.path.join(PAGES_FOLDER, "page_structure.json")

    if not group_name:
        flash("Missing group name.")
        return redirect(url_for('developer.developer_dashboard'))

    if not os.path.exists(structure_path):
        flash("Structure file missing.")
        return redirect(url_for('developer.developer_dashboard'))

    with open(structure_path) as f:
        structure = json.load(f)

    moved_pages = []

    # 1. Extract pages from the group to delete
    new_structure = []
    for group in structure:
        if group["group"] == group_name:
            moved_pages = group["pages"]
        else:
            new_structure.append(group)

    # 2. Find or create "Ungrouped"
    ungrouped = next((g for g in new_structure if g["group"] == "Ungrouped"), None)
    if ungrouped:
        ungrouped["pages"].extend(moved_pages)
    else:
        new_structure.append({"group": "Ungrouped", "pages": moved_pages})

    # 3. Save updated structure
    with open(structure_path, 'w') as f:
        json.dump(new_structure, f, indent=2)

    flash(f"Group '{group_name}' deleted. Pages moved to 'Ungrouped'.")
    return redirect(url_for('developer.developer_dashboard'))
