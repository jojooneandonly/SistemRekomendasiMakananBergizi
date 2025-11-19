import math
import json
import os
import random
import pandas as pd 
# Import Flask dan send_file untuk melayani HTML dari root
from flask import Flask, request, jsonify, send_file 

# --- INISIALISASI FLASK ---
# Inisialisasi tanpa folder template/static eksplisit
app = Flask(__name__) 

# --- KONSTANTA DAN INISIALISASI DATABASE ---
MAKANAN_DATABASE = {}
EXCEL_FILE_NAME = "makanan_database.xlsx"

try:
    df = pd.read_excel(EXCEL_FILE_NAME)
    for index, row in df.iterrows():
        nama_makanan = row['Nama Makanan']
        MAKANAN_DATABASE[nama_makanan] = {
            "jenis": row['jenis'],
            "karbo": row['karbo'],
            "protein": row['protein'],
            "kalori": row['kalori']
        }
    print(f"Data makanan berhasil dimuat dari {EXCEL_FILE_NAME}. Total {len(MAKANAN_DATABASE)} item.")
except FileNotFoundError:
    print(f"Gagal memuat file Excel. File '{EXCEL_FILE_NAME}' tidak ditemukan. Program berjalan dengan database kosong.")
except Exception as e:
    print(f"Terjadi kesalahan saat memproses Excel: {e}")

# Faktor Aktivitas yang sudah diperluas
FAKTOR_AKTIVITAS = {
    "sangat_ringan": 1.2,
    "ringan": 1.375,
    "sedang": 1.55,
    "berat": 1.725,
    "sangat_berat": 2.0 
}

# ... (Semua konstanta dan fungsi perhitungan gizi lainnya) ...
# (Saya memangkas fungsi di sini untuk menghemat ruang, asumsikan semua fungsi hitung_imt, hitung_tdee, dll. ada di sini)
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

SAVE_FILE = "last_food.json"

def load_last_food():
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, "r") as f:
            try:
                data = json.load(f)
                if isinstance(data, dict): return data
            except Exception: pass
    return {}

def save_last_food(data):
    with open(SAVE_FILE, "w") as f:
        json.dump(data, f, indent=2)

def pilih_acak_berbeda(kategori_list, last_list):
    if not isinstance(last_list, list): last_list = []
    available = [m for m in kategori_list if m not in last_list]
    if len(available) < 3 and len(kategori_list) >= 3:
        available = kategori_list.copy()
    n = min(3, len(available))
    if n == 0 and len(kategori_list) > 0:
        available = kategori_list.copy()
        n = min(3, len(available))
    if n > 0:
        return random.sample(available, n)
    else:
        return []

def rekomendasikan_makanan(makro_target):
    if not MAKANAN_DATABASE:
        return {
            "Protein": f"{makro_target.get('protein', {'gram': 0})['gram']} gram/hari → (Database Kosong)",
            "Karbohidrat": f"{makro_target.get('karbohidrat', {'gram': 0})['gram']} gram/hari → (Database Kosong)",
            "Lemak Sehat": f"{makro_target.get('lemak', {'gram': 0})['gram']} gram/hari → (Database Kosong)",
            "Sayuran": "2 porsi/hari → (Database Kosong)",
            "Buah": "2 porsi/hari → (Database Kosong)",
        }
        
    last = load_last_food()
    target_protein = makro_target['protein']['gram']
    target_karbo = makro_target['karbohidrat']['gram']
    target_lemak = makro_target['lemak']['gram']

    protein_items = [m for m, v in MAKANAN_DATABASE.items() if v.get("jenis") and "Protein" in v["jenis"]]
    karbo_items = [m for m, v in MAKANAN_DATABASE.items() if v.get("jenis") == "Karbohidrat"]
    lemak_items = [m for m, v in MAKANAN_DATABASE.items() if v.get("jenis") == "Lemak Sehat"]
    sayur_items = [m for m, v in MAKANAN_DATABASE.items() if v.get("jenis") == "Sayur"]
    buah_items = [m for m, v in MAKANAN_DATABASE.items() if v.get("jenis") == "Buah"]

    protein_final = pilih_acak_berbeda(protein_items, last.get("Protein", []))
    karbo_final = pilih_acak_berbeda(karbo_items, last.get("Karbohidrat", []))
    lemak_final = pilih_acak_berbeda(lemak_items, last.get("Lemak", []))
    sayur_final = pilih_acak_berbeda(sayur_items, last.get("Sayur", []))
    buah_final = pilih_acak_berbeda(buah_items, last.get("Buah", []))

    save_last_food({
        "Protein": protein_final, "Karbohidrat": karbo_final, "Lemak": lemak_final, 
        "Sayur": sayur_final, "Buah": buah_final
    })

    rekom = {}
    rekom["Protein"] = f"{target_protein} gram/hari → {', '.join(protein_final)}"
    rekom["Karbohidrat"] = f"{target_karbo} gram/hari → {', '.join(karbo_final)}"
    rekom["Lemak Sehat"] = f"{target_lemak} gram/hari → {', '.join(lemak_final)}"
    rekom["Sayuran"] = f"2 porsi/hari → {', '.join(sayur_final)}"
    rekom["Buah"] = f"2 porsi/hari → {', '.join(buah_final)}"

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

    try:
        imt = hitung_imt(berat, tinggi)
        status, saran = klasifikasi_imt(imt)
        bbi = hitung_bbi(tinggi, jk) 
        bmr = hitung_bmr(bbi, tinggi, usia, jk)
        tdee = hitung_tdee(bmr, aktivitas)
        makro = hitung_makronutrien(tdee)
        rekom = rekomendasikan_makanan(makro)
    except Exception as e:
        print(f"Error saat perhitungan: {e}")
        return jsonify({"error": f"Terjadi kesalahan saat perhitungan gizi: {e}"}), 500

    return jsonify({
        'imt': imt, 'status': status, 'saran': saran, 'tdee': tdee, 
        'makro': makro, 'rekomendasi': rekom
    })

if __name__ == '__main__':
    app.run(debug=True)