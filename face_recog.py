import face_recognition
import cv2
import numpy as np
import os
import sqlite3

def load_known_faces():
    known_face_encodings = []
    known_face_names = []
    known_face_rolls = []
    
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    
    c.execute("SELECT name, roll_no, face_encoding FROM students")
    for name, roll_no, encoding_bytes in c.fetchall():
        encoding = np.frombuffer(encoding_bytes, dtype=np.float64)
        known_face_encodings.append(encoding)
        known_face_names.append(name)
        known_face_rolls.append(roll_no)
    
    conn.close()
    return known_face_encodings, known_face_names, known_face_rolls

def process_group_photo(image_path):
    # Load known faces
    known_face_encodings, known_face_names, known_face_rolls = load_known_faces()
    
    # Load the uploaded image
    image = face_recognition.load_image_file(image_path)
    
    # Find all face locations and encodings
    face_locations = face_recognition.face_locations(image)
    face_encodings = face_recognition.face_encodings(image, face_locations)
    
    present_rolls = []
    
    for face_encoding in face_encodings:
        # Compare with known faces
        matches = face_recognition.compare_faces(known_face_encodings, face_encoding, tolerance=0.6)
        face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
        
        best_match_index = np.argmin(face_distances)
        if matches[best_match_index]:
            present_rolls.append(known_face_rolls[best_match_index])
    
    return present_rolls

def add_student_face(name, roll_no, image_path):
    image = face_recognition.load_image_file(image_path)
    face_encodings = face_recognition.face_encodings(image)
    
    if len(face_encodings) == 0:
        return False
    
    encoding_bytes = face_encodings[0].tobytes()
    
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    
    try:
        c.execute("INSERT INTO students (name, roll_no, face_encoding) VALUES (?, ?, ?)",
                 (name, roll_no, encoding_bytes))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False