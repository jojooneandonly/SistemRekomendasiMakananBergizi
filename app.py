import math
import json
import os
import random
import pandas as pd 
import hashlib # Tambahkan import ini untuk membuat seed yang konsisten
from flask import Flask, request, jsonify, send_file 

# --- INISIALISASI FLASK ---
app = Flask(__name__) 

# --- KONSTANTA DAN INISIALISASI DATABASE ---
# Data Makanan statis diambil dari JavaScript untuk memastikan konsistensi dan deterministik
FOOD_OPTIONS = {
    "Protein": ["Dada ayam tanpa kulit", "Ikan (Salmon, Tuna)", "Telur", "Tempe/Tahu", "Yogurt Yunani"],
    "Karbohidrat": ["Nasi merah/cokelat", "Oatmeal", "Ubi jalar", "Roti gandum utuh", "Quinoa"],
    "Lemak Sehat": ["Alpukat", "Minyak Zaitun (Extra Virgin)", "Kacang-kacangan (Almond, Kenari)", "Biji Chia/Flaxseed", "Ikan Berlemak"],
    "Sayuran": ["Brokoli", "Bayam", "Wortel", "Tomat", "Kale", "Paprika"],
    "Buah": ["Apel", "Pisang", "Jeruk", "Berry (Stroberi, Blueberry)", "Mangga", "Pir"]
}

# Faktor Aktivitas yang sudah diperluas
FAKTOR_AKTIVITAS = {
    "sangat_ringan": 1.2,
    "ringan": 1.375,
    "sedang": 1.55,
    "berat": 1.725,
    "sangat_berat": 2.0 
}

# --- FUNGSI PERHITUNGAN GIZI ---

def hitung_imt(berat_kg, tinggi_cm):
    tinggi_meter = tinggi_cm / 100
    if tinggi_meter <= 0: return 0
    imt = berat_kg / (tinggi_meter ** 2)
    return round(imt, 2)

def klasifikasi_imt(imt):
    if imt < 18.5: return "Underweight (Kurus)", "Perlu peningkatan berat badan dan asupan gizi."
    elif 18.5 <= imt < 25.0: return "Normal (Ideal)", "Pertahankan pola hidup dan asupan gizi seimbang."
    elif 25.0 <= imt < 30.0: return "Overweight", "Kurangi kalori dan tingkatkan aktivitas fisik."
    else: return "Obesitas", "Perlu konsultasi gizi & perbaikan pola makan."

def hitung_bbi(tinggi_cm, jenis_kelamin):
    tinggi_kurang_100 = tinggi_cm - 100
    if jenis_kelamin.lower() == 'pria':
        bbi = tinggi_kurang_100 - (0.10 * tinggi_kurang_100)
    else:
        bbi = tinggi_kurang_100 - (0.15 * tinggi_kurang_100)
    return max(40, round(bbi))

def hitung_bmr(bbi, tinggi_cm, usia, jenis_kelamin):
    if jenis_kelamin.lower() == 'pria':
        bmr = (10 * bbi) + (6.25 * tinggi_cm) - (5 * usia) + 5
    else:
        bmr = (10 * bbi) + (6.25 * tinggi_cm) - (5 * usia) - 161
    return round(bmr)

def hitung_tdee(bmr, aktivitas):
    faktor = FAKTOR_AKTIVITAS.get(aktivitas, 1.375)
    tdee = bmr * faktor
    return round(tdee)

def hitung_makronutrien(tdee):
    hasil = {}
    RASIO_MAKRO = {"karbohidrat": 0.55, "protein": 0.25, "lemak": 0.20}
    KALORI_PER_GRAM = {"karbohidrat": 4, "protein": 4, "lemak": 9}
    for nutrisi, rasio in RASIO_MAKRO.items():
        kalori_nutrisi = tdee * rasio
        gram = kalori_nutrisi / KALORI_PER_GRAM[nutrisi]
        hasil[nutrisi] = {"gram": round(gram), "kalori": round(kalori_nutrisi), "rasio": rasio * 100}
    return hasil

def rekomendasikan_makanan(makro_target, input_string):
    """
    Menghasilkan rekomendasi makanan yang deterministik (konsisten) 
    berdasarkan input_string (semua input pengguna).
    """
    # 1. Buat Seed Unik dari semua input
    seed_value = int(hashlib.sha1(input_string.encode('utf-8')).hexdigest(), 16) % (10**8)
    random.seed(seed_value) 

    rekom = {}
    
    # Kunci untuk target makro
    makro_keys = {
        "Protein": makro_target['protein']['gram'], 
        "Karbohidrat": makro_target['karbohidrat']['gram'], 
        "Lemak Sehat": makro_target['lemak']['gram']
    }

    # 2. Lakukan Pemilihan Acak (tapi konsisten karena sudah di-seed)
    for category, options in FOOD_OPTIONS.items():
        n = min(3, len(options))
        # random.sample akan menghasilkan hasil yang sama untuk seed yang sama
        selected_items = random.sample(options, n)
        
        # 3. Format Output
        if category in makro_keys:
            target_gram = makro_keys[category]
            rekom[category] = f"{target_gram} gram/hari → {', '.join(selected_items)}"
        elif category == "Sayuran" or category == "Buah":
            rekom[category] = f"2 porsi/hari → {', '.join(selected_items)}"
            
    return rekom

# --- LOGIKA FLASK API ---

@app.route('/')
def home():
    """Melayani file index.html dari root folder."""
    return send_file('index.html')

@app.route('/calculate', methods=['POST'])
def calculate_nutrition():
    """Menerima data dari form, menjalankan perhitungan, dan mengembalikan hasil JSON."""
    data = request.get_json()
    
    try:
        tinggi = float(data.get('tinggi'))
        berat = float(data.get('berat'))
        usia = int(data.get('usia'))
        jk = data.get('jk').lower()
        aktivitas = data.get('aktivitas').lower()
    except (ValueError, TypeError):
        return jsonify({"error": "Data input harus berupa angka yang valid."}), 400

    if jk not in ['pria', 'wanita'] or aktivitas not in FAKTOR_AKTIVITAS:
        return jsonify({"error": "Jenis kelamin atau aktivitas tidak valid."}), 400
    
    if tinggi <= 100 or usia <= 10 or berat < 20:
        return jsonify({"error": "Input tinggi/usia/berat tidak valid."}), 400

    # Gabungkan semua input menjadi string unik untuk seeding
    input_string = f"{tinggi}-{berat}-{usia}-{jk}-{aktivitas}" 

    try:
        imt = hitung_imt(berat, tinggi)
        status, saran = klasifikasi_imt(imt)
        bbi = hitung_bbi(tinggi, jk) 
        bmr = hitung_bmr(bbi, tinggi, usia, jk)
        tdee = hitung_tdee(bmr, aktivitas)
        makro = hitung_makronutrien(tdee)
        
        # Kirim input_string ke fungsi rekomendasi
        rekom = rekomendasikan_makanan(makro, input_string) 
    except Exception as e:
        print(f"Error saat perhitungan: {e}")
        return jsonify({"error": f"Terjadi kesalahan saat perhitungan gizi: {e}"}), 500

    return jsonify({
        'imt': imt, 'status': status, 'saran': saran, 'tdee': tdee, 
        'makro': makro, 'rekomendasi': rekom
    })

if __name__ == '__main__':
    app.run(debug=True)
