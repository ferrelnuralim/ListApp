import io
import re
import pdfplumber
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Generator List Poli Bedah Mulut", layout="centered")

st.title("Generator List Poli Bedah Mulut")
st.caption("Upload file PDF (seperti '18 akhir.pdf' / '19sept2025.pdf'), saya buatkan list pasien per DPJP dengan urutan sesuai hierarki.")

DOCTOR_PRIORITY = [
    "drg. Andi Tajrin, M.Kes., Sp.B.M.M., Subsp. C.O.M.(K)",
    "drg. Mohammad Gazali, MARS., Sp.B.M.M., Subsp.T.M.T.M.J.(K)",
    "drg. Yossy Yoanita Ariestiana, M.KG., Sp.B.M.M., Subsp.Ortognat-D (K)",
    "drg. Abul Fauzi, Sp.B.M.M., Subsp.T.M.T.M.J.(K)",
    "drg. M. Irfan Rasul, Ph.D., Sp.B.M.M., Subsp.C.O.M.(K)",
    "drg. Nurwahida, M.K.G., Sp.B.M.M., Subsp.C.O.M(K)",
    "drg. Hadira, M.K.G., Sp.B.M.M., Subsp.C.O.M(K)",
    "drg. Mukhtar Nur Anam Sp.B.M.M.",
    "drg. Timurwati, Sp.B.M.M.",
    "drg. Husnul Basyar, Sp. B.M.M.",
    "drg. Husni Mubarak, Sp. B.M.M.",
    "drg. Carolina Stevanie, Sp.B.M.M.",
]

def normalize_text(s: str) -> str:
    if s is None:
        return ""
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    s = s.replace("drg..", "drg.")
    s = re.sub(r",(?=\S)", ", ", s)
    s = s.replace("Sp.BMM", "Sp.B.M.M.")
    s = s.replace("Sp. B.M.M.", "Sp. B.M.M.")
    s = s.replace("M.Kes.,Sp.", "M.Kes., Sp.")
    s = s.replace("M.K.G., Sp", "M.K.G., Sp")
    s = s.replace("Subsp.C.O.M(K)", "Subsp. C.O.M.(K)")
    s = s.replace("Subsp.C.O.M.(K)", "Subsp. C.O.M.(K)")
    s = s.replace("Subsp.T.M.T.M.J.(K)", "Subsp.T.M.T.M.J.(K)")
    return s

def map_doctor_to_canonical(name: str) -> str:
    raw = normalize_text(name)
    for can in DOCTOR_PRIORITY:
        if raw == can:
            return can
    lower = raw.lower()
    if "tajrin" in lower: return DOCTOR_PRIORITY[0]
    if "gazali" in lower: return DOCTOR_PRIORITY[1]
    if "yossy" in lower or "yoanita" in lower: return DOCTOR_PRIORITY[2]
    if "abul" in lower or "fauzi" in lower: return DOCTOR_PRIORITY[3]
    if "irfan" in lower and "rasul" in lower: return DOCTOR_PRIORITY[4]
    if "nurwahida" in lower: return DOCTOR_PRIORITY[5]
    if "hadira" in lower: return DOCTOR_PRIORITY[6]
    if "mukhtar" in lower or "anam" in lower: return DOCTOR_PRIORITY[7]
    if "timurwati" in lower: return DOCTOR_PRIORITY[8]
    if "husnul" in lower and "basyar" in lower: return DOCTOR_PRIORITY[9]
    if "husni" in lower and "mubarak" in lower: return DOCTOR_PRIORITY[10]
    if "carolina" in lower and "stevanie" in lower: return DOCTOR_PRIORITY[11]
    return raw

def extract_all_tables_from_pdf(file_bytes: bytes) -> pd.DataFrame:
    wanted_cols = {"No.", "No. RM", "Nama Pasien", "Dokter"}
    frames = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            try:
                tables = page.extract_tables()
            except Exception:
                tables = []
            for t in (tables or []):
                if not t or not t[0]:
                    continue
                header = [str(x).strip() if x is not None else "" for x in t[0]]
                if "Dokter" in header and "Nama Pasien" in header:
                    data_rows = t[1:]
                    norm = []
                    for r in data_rows:
                        r = [(str(x) if x is not None else "").strip() for x in r]
                        if len(r) < len(header):
                            r = r + [""]*(len(header)-len(r))
                        elif len(r) > len(header):
                            r = r[:len(header)]
                        norm.append(r)
                    df = pd.DataFrame(norm, columns=header)
                    frames.append(df)
    if not frames:
        return pd.DataFrame(columns=list(wanted_cols))
    big = pd.concat(frames, ignore_index=True, sort=False)
    keep = [c for c in big.columns if c in wanted_cols]
    out = big[keep].copy()
    for c in ["No.", "No. RM", "Nama Pasien", "Dokter"]:
        if c not in out:
            out[c] = ""
    for c in out.columns:
        out[c] = out[c].astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
    out["No_num"] = pd.to_numeric(out["No."], errors="coerce")
    return out

uploaded_files = st.file_uploader("Upload PDF (bisa lebih dari satu)", type=["pdf"], accept_multiple_files=True)
title = st.text_input("Judul (opsional)", "LIST PASIEN POLI BEDAH MULUT")
subtitle = st.text_input("Subjudul (opsional)", "Jumat, 19/09/2025")
add_check = st.checkbox("Tambahkan emoji centang (✅) di akhir nama", value=True)

if st.button("Generate List"):
    if not uploaded_files:
        st.warning("Silakan upload minimal 1 file PDF.")
        st.stop()
    pieces = []
    for up in uploaded_files:
        df = extract_all_tables_from_pdf(up.getvalue())
        if not df.empty:
            pieces.append(df)
    if not pieces:
        st.error("Tidak menemukan tabel yang sesuai di PDF yang diupload.")
        st.stop()
    df_all = pd.concat(pieces, ignore_index=True)
    df_all["Dokter_canon"] = df_all["Dokter"].apply(map_doctor_to_canonical)

    doctors_in_data = list(dict.fromkeys(df_all["Dokter_canon"].tolist()))
    ordered = [d for d in DOCTOR_PRIORITY if d in doctors_in_data] + [d for d in doctors_in_data if d not in DOCTOR_PRIORITY]

    lines = []
    if title and subtitle:
        lines.append(f"{title}, {subtitle}\n")
    elif title:
        lines.append(f"{title}\n")
  counter = 1
for d in ordered:
    # Bold untuk WhatsApp (pakai asterisk di kiri-kanan)
    lines.append(f"*{d}*")
    sub = df_all[df_all["Dokter_canon"] == d].copy().sort_values(by=["No_num"], na_position="last")
    for _, row in sub.iterrows():
        tail = "✅" if add_check else ""
        lines.append(f"{counter}\t{row['No. RM']}\t{row['Nama Pasien']}{tail}")
        counter += 1
    lines.append("")  # spasi antar DPJP

    st.text_area("Hasil", final_text, height=400)
    st.download_button("Download TXT", data=final_text.encode("utf-8"), file_name="LIST_PASIEN_POLI_BM.txt", mime="text/plain")
