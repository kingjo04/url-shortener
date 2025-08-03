from flask import Flask, request, redirect, render_template, session, url_for, send_file, Response
from urllib.parse import urlparse
import string
import random
import re
from supabase import create_client, Client
import os
from dotenv import load_dotenv
import logging
import io

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Ganti dengan secret key aman di production

# Setup logging
logging.basicConfig(level=logging.DEBUG)

# Muat file .env
load_dotenv()

# Inisialisasi Supabase
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

# Validasi kredensial Supabase
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL dan SUPABASE_KEY harus diatur di file .env. Pastikan file .env ada di direktori proyek dan berisi nilai yang benar.")

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    raise ValueError(f"Gagal menginisialisasi Supabase: {str(e)}")

# Generate kode pendek acak
def generate_short_code(length=6):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

# Validasi kode kustom
def is_valid_custom_code(code):
    return bool(re.match(r'^[a-zA-Z0-9_-]{3,10}$', code))

# Cek apakah kode sudah ada
def code_exists(short_code):
    try:
        response = supabase.table('links').select('short_code').eq('short_code', short_code).execute()
        return len(response.data) > 0
    except Exception as e:
        logging.error(f"Error saat cek kode: {str(e)}")
        return False

# Cek apakah email sudah ada
def email_exists(email):
    try:
        response = supabase.table('users').select('email').eq('email', email).execute()
        return len(response.data) > 0
    except Exception as e:
        logging.error(f"Error saat cek email: {str(e)}")
        return False

# Simpan ke database
def store_link(short_code, content_type, content, user_id):
    try:
        supabase.table('links').insert({
            'short_code': short_code,
            'content_type': content_type,
            'content': content,
            'user_id': user_id
        }).execute()
        logging.debug(f"Stored link: short_code={short_code}, content_type={content_type}, content={content}, user_id={user_id}")
    except Exception as e:
        logging.error(f"Error saat menyimpan link: {str(e)}")
        raise

# Hapus link dan file (jika ada)
def delete_link(short_code, user_id):
    try:
        # Ambil data link
        response = supabase.table('links').select('*').eq('short_code', short_code).eq('user_id', user_id).execute()
        if not response.data:
            return False
        link = response.data[0]
        # Hapus file dari storage jika gambar/dokumen
        if link['content_type'] in ('image', 'document'):
            file_name = link['content'].split('/content/')[-1]
            supabase.storage.from_('content').remove([file_name])
        # Hapus dari tabel links
        supabase.table('links').delete().eq('short_code', short_code).eq('user_id', user_id).execute()
        logging.debug(f"Deleted link: short_code={short_code}, user_id={user_id}")
        return True
    except Exception as e:
        logging.error(f"Error saat hapus link: {str(e)}")
        return False

# Modifikasi short_code
def update_short_code(old_code, new_code, user_id):
    try:
        if code_exists(new_code):
            return False, "Kode kustom sudah digunakan!"
        if not is_valid_custom_code(new_code):
            return False, "Kode kustom tidak valid! Gunakan 3-10 karakter (huruf, angka, _, -)."
        supabase.table('links').update({'short_code': new_code}).eq('short_code', old_code).eq('user_id', user_id).execute()
        logging.debug(f"Updated short_code: {old_code} to {new_code}, user_id={user_id}")
        return True, None
    except Exception as e:
        logging.error(f"Error saat update short_code: {str(e)}")
        return False, str(e)

# Route untuk halaman utama
@app.route('/')
def index():
    user = session.get('user')
    return render_template('index.html', user=user)

# Route untuk register
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        if email_exists(email):
            return render_template('register.html', error='Email sudah digunakan!')
        try:
            response = supabase.table('users').insert({
                'email': email,
                'password': password  # Simpan password langsung (tidak aman untuk produksi)
            }).execute()
            user_id = response.data[0]['id']
            session['user'] = {'email': email, 'id': user_id}
            return redirect(url_for('index'))
        except Exception as e:
            logging.error(f"Error saat register: {str(e)}")
            return render_template('register.html', error=str(e))
    return render_template('register.html')

# Route untuk login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        response = supabase.table('users').select('*').eq('email', email).eq('password', password).execute()
        if response.data:
            session['user'] = {'email': email, 'id': response.data[0]['id']}
            return redirect(url_for('index'))
        return render_template('login.html', error='Email atau password salah!')
    return render_template('login.html')

# Route untuk logout
@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))

# Route untuk dashboard
@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    user_id = session['user']['id']
    response = supabase.table('links').select('*').eq('user_id', user_id).execute()
    links = response.data
    return render_template('dashboard.html', user=session['user'], links=links)

# Route untuk memendekkan konten
@app.route('/shorten', methods=['POST'])
def shorten():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    content_type = request.form['content_type']
    custom_code = request.form.get('custom_code', '').strip()
    user_id = session['user']['id']
    
    # Validasi kode kustom
    if custom_code:
        if not is_valid_custom_code(custom_code):
            return render_template('index.html', user=session['user'], error='Kode kustom tidak valid! Gunakan 3-10 karakter (huruf, angka, _, -).')
        if code_exists(custom_code):
            return render_template('index.html', user=session['user'], error='Kode kustom sudah digunakan! Coba kode lain.')
        short_code = custom_code
    else:
        while True:
            short_code = generate_short_code()
            if not code_exists(short_code):
                break

    # Proses konten
    content = ''
    if content_type == 'url':
        content = request.form.get('url', '')
        if not content.startswith(('http://', 'https://')):
            content = 'http://' + content
    elif content_type == 'text':
        content = request.form.get('text', '')
    elif content_type in ('image', 'document'):
        file = request.files.get('file')
        if file:
            # Validasi tipe file dan ukuran
            allowed_extensions = {
                'image': ['jpg', 'jpeg', 'png'],
                'document': ['pdf', 'docx']
            }
            file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
            if file_ext not in allowed_extensions[content_type]:
                return render_template('index.html', user=session['user'], error=f'File tidak valid! Gunakan {", ".join(allowed_extensions[content_type])} untuk {content_type}.')
            
            # Validasi ukuran file (maks 10MB)
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)
            if file_size > 10 * 1024 * 1024:  # 10MB dalam bytes
                return render_template('index.html', user=session['user'], error='File terlalu besar! Maksimum 10MB.')
            
            file_name = f"{user_id}/{short_code}_{file.filename.replace(' ', '_')}"
            content_type_map = {
                'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg',
                'png': 'image/png',
                'pdf': 'application/pdf',
                'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            }
            try:
                # Upload file ke Supabase Storage
                file_content = file.read()
                logging.debug(f"Uploading file: {file_name}, size: {len(file_content)} bytes, extension: {file_ext}, content_type: {content_type_map.get(file_ext, file.content_type)}")
                response = supabase.storage.from_('content').upload(
                    file_name,
                    file_content,
                    {'content-type': content_type_map.get(file_ext, file.content_type)}
                )
                logging.debug(f"Supabase upload response: {response}")
                # Dapatkan URL publik
                content = f"{SUPABASE_URL}/storage/v1/object/public/content/{file_name}"
                logging.debug(f"Generated public URL: {content}")
                # Verifikasi URL publik
                test_response = supabase.storage.from_('content').get_public_url(file_name)
                logging.debug(f"Test public URL response: {test_response}")
            except Exception as e:
                logging.error(f"Error saat upload file: {str(e)}")
                return render_template('index.html', user=session['user'], error=f'Gagal mengunggah file: {str(e)}')
        else:
            return render_template('index.html', user=session['user'], error='Harap unggah file!')

    if not content:
        return render_template('index.html', user=session['user'], error='Konten tidak valid! Pastikan URL, teks, atau file diisi.')

    # Simpan ke database
    try:
        store_link(short_code, content_type, content, user_id)
    except Exception as e:
        return render_template('index.html', user=session['user'], error=f'Gagal menyimpan link: {str(e)}')

    # Buat link pendek
    domain = urlparse(request.base_url).netloc
    short_url = f"http://{domain}/{short_code}"
    logging.debug(f"Generated short URL: {short_url}")

    return render_template('index.html', user=session['user'], short_url=short_url, success=f'Berhasil memendekkan! Link Anda: {short_url}')

# Route untuk menampilkan konten
@app.route('/<short_code>')
def redirect_url(short_code):
    response = supabase.table('links').select('*').eq('short_code', short_code).execute()
    if not response.data:
        return render_template('404.html'), 404

    link = response.data[0]
    content_type = link['content_type']
    content = link['content']
    logging.debug(f"Redirecting to: short_code={short_code}, content_type={content_type}, content={content}")

    return render_template('content.html', content_type=content_type, content=content)

# Route untuk download file
@app.route('/download/<short_code>')
def download(short_code):
    response = supabase.table('links').select('*').eq('short_code', short_code).execute()
    if not response.data:
        return render_template('404.html'), 404

    link = response.data[0]
    if link['content_type'] not in ('image', 'document'):
        return redirect(url_for('dashboard', error='Konten bukan file yang bisa diunduh!'))

    file_name = link['content'].split('/content/')[-1]
    try:
        # Download file dari Supabase Storage
        file_data = supabase.storage.from_('content').download(file_name)
        file_ext = file_name.rsplit('.', 1)[1].lower() if '.' in file_name else ''
        content_type_map = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'pdf': 'application/pdf',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        }
        return Response(
            file_data,
            mimetype=content_type_map.get(file_ext, 'application/octet-stream'),
            headers={'Content-Disposition': f'attachment; filename={file_name.split("/")[-1]}'}
        )
    except Exception as e:
        logging.error(f"Error saat download file: {str(e)}")
        return redirect(url_for('dashboard', error=f'Gagal mengunduh file: {str(e)}'))

# Route untuk hapus link
@app.route('/delete/<short_code>', methods=['POST'])
def delete(short_code):
    if 'user' not in session:
        return redirect(url_for('login'))
    user_id = session['user']['id']
    if delete_link(short_code, user_id):
        return redirect(url_for('dashboard', success='Link berhasil dihapus!'))
    return redirect(url_for('dashboard', error='Gagal menghapus link!'))

# Route untuk modifikasi short_code
@app.route('/update/<short_code>', methods=['POST'])
def update(short_code):
    if 'user' not in session:
        return redirect(url_for('login'))
    user_id = session['user']['id']
    new_code = request.form.get('new_code', '').strip()
    success, message = update_short_code(short_code, new_code, user_id)
    if success:
        return redirect(url_for('dashboard', success='Link berhasil diperbarui!'))
    return redirect(url_for('dashboard', error=message))

if __name__ == '__main__':
    app.run(debug=True)