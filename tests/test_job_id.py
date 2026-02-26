from job_hunter.data_manager import DataManager
import os

def test_job_id_generation():
    db = DataManager()

    # Test base ID
    id1 = db.generate_job_id("Software Engineer", "Google")
    assert id1 == "Software Engineer-Google"

    # Test with resume
    id2 = db.generate_job_id("Software Engineer", "Google", "MyResume.pdf")
    assert id2 == "Software Engineer-Google-MyResume"

    # Test with spaces
    id3 = db.generate_job_id(" Software Engineer  ", "  Google  ")
    assert id3 == "Software Engineer-Google"

    # Test with None
    id4 = db.generate_job_id(None, None)
    assert id4 == "Unknown-Unknown"

    print("✅ All Job ID tests passed!")

if __name__ == "__main__":
    test_job_id_generation()
