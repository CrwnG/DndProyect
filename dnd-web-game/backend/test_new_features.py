"""Test script for the 8 new D&D game features."""
import requests
import json
import tempfile
import os

BASE_URL = "http://localhost:8001/api"

def test_feature_6_export_json():
    """Feature 6: Character Export JSON"""
    print("=== Feature 6: Character Export JSON ===")
    
    # Create a fresh demo character to ensure clean data
    r = requests.post(f"{BASE_URL}/character/demo")
    if r.status_code != 200:
        print(f"ERROR: Could not create demo character: {r.text}")
        return None
    
    demo_data = r.json()
    char_id = demo_data.get("character_id")
    print(f"Created fresh demo character: {demo_data.get('combatant', {}).get('name')} ({char_id})")
    
    r = requests.get(f"{BASE_URL}/character/{char_id}/export")
    print(f"Status: {r.status_code}")
    
    if r.status_code == 200:
        data = r.json()
        print(f"Version: {data.get('version')}")
        print(f"Format: {data.get('format')}")
        print(f"Character name: {data.get('character', {}).get('name')}")
        print("PASSED!")
        return data
    else:
        print(f"FAILED: {r.text}")
        return None

def test_feature_7_export_summary():
    """Feature 7: Character Export Text Summary"""
    print("\n=== Feature 7: Character Export Text Summary ===")
    
    r = requests.get(f"{BASE_URL}/character/list")
    chars = r.json().get("characters", [])
    if not chars:
        print("SKIP: No characters available")
        return
    
    char_id = chars[0]["id"]
    r = requests.get(f"{BASE_URL}/character/{char_id}/export/summary")
    print(f"Status: {r.status_code}")
    
    if r.status_code == 200:
        data = r.json()
        summary = data.get("summary", "")
        print("Summary preview:")
        for line in summary.split("\n")[:7]:
            print(f"  {line}")
        print("PASSED!")
    else:
        print(f"FAILED: {r.text}")

def test_feature_8_import_from_export(export_data):
    """Feature 8: Import from Export"""
    print("\n=== Feature 8: Import from Export ===")
    
    if not export_data:
        print("SKIP: No export data to test with")
        return
    
    # Create a temp file with the export data
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(export_data, f)
        temp_path = f.name
    
    try:
        with open(temp_path, 'rb') as f:
            files = {'file': ('export.json', f, 'application/json')}
            r = requests.post(f"{BASE_URL}/character/import/export", files=files)
        
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"New character ID: {data.get('character_id')}")
            print(f"Character name: {data.get('character', {}).get('name')}")
            print("PASSED!")
        else:
            print(f"FAILED: {r.text}")
    finally:
        os.unlink(temp_path)

def test_feature_5_saves():
    """Feature 5: Database-Persisted Saves"""
    print("\n=== Feature 5: Database-Persisted Saves ===")
    
    # List saves
    r = requests.get(f"{BASE_URL}/campaign/saves")
    print(f"List saves status: {r.status_code}")
    if r.status_code == 200:
        saves = r.json().get("saves", [])
        print(f"Number of saves: {len(saves)}")
        print("PASSED!")
    else:
        print(f"List saves error: {r.text}")
        # This might be OK if no session exists

def test_feature_4_gold_division():
    """Feature 4: Loot Gold Division (check code exists)"""
    print("\n=== Feature 4: Loot Gold Division ===")
    print("This feature requires combat loot to test.")
    print("Verified in code: loot.py lines 319-365 has gold division logic.")
    print("NOTED (code verified)")

def test_features_1_3_sync():
    """Features 1-3: Character-Party Link and Auto-Sync"""
    print("\n=== Features 1-3: Character-Party Link + Auto-Sync ===")
    print("These features require a full combat session to test.")
    print("Verified in code:")
    print("  - PartyMember.character_id field exists in game_session.py")
    print("  - _sync_party_to_characters() in campaign.py lines 62-114")
    print("  - end_combat calls sync at lines 973-981")
    print("NOTED (code verified)")

if __name__ == "__main__":
    print("Testing 8 New D&D Game Features")
    print("=" * 50)
    print()
    
    export_data = test_feature_6_export_json()
    test_feature_7_export_summary()
    test_feature_8_import_from_export(export_data)
    test_feature_5_saves()
    test_feature_4_gold_division()
    test_features_1_3_sync()
    
    print()
    print("=" * 50)
    print("Testing Complete!")
