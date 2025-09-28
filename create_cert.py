from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
import json
import hashlib
import datetime
from database import create_connection, close_connection

# Define the blueprint
create_cert_bp = Blueprint('create_cert', __name__, template_folder='templates')

def generate_hash(data_string):
    """Generate SHA-256 hash for the given data"""
    return hashlib.sha256(data_string.encode()).hexdigest()

def get_last_block_hash():
    """Get the hash of the last block in the blockchain"""
    conn = create_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT current_hash FROM blocks ORDER BY id DESC LIMIT 1")
        result = cursor.fetchone()
        
        if result:
            return result[0]
        else:
            # Genesis block case
            return "0"
    except Exception as e:
        print(f"Error getting last block hash: {e}")
        return "0"
    finally:
        close_connection(conn)

@create_cert_bp.route('/')
def homepage():
    """Render the homepage template"""
    return render_template('homepage.html')

@create_cert_bp.route('/create_certificate', methods=['GET', 'POST'])
def create_certificate():
    """Create a new certificate and add it to the blockchain"""
    
    if request.method == 'POST':
        # Get form data
        student_name = request.form.get('student_name')
        course = request.form.get('course')
        
        if not student_name or not course:
            flash('Please fill in all fields', 'error')
            return render_template('homepage.html')
        
        try:
            conn = create_connection()
            cursor = conn.cursor()
            
            # Generate certificate data
            issued_date = datetime.datetime.now()
            certificate_data = {
                'certificate_id': None,  # Will be set after certificate insertion
                'student': student_name,
                'course': course,
                'issued_date': issued_date.isoformat()
            }
            
            # First, create the certificate record
            certificate_data_str = f"{student_name}{course}{issued_date.isoformat()}"
            certificate_hash = generate_hash(certificate_data_str)
            
            # Insert into certificates table
            cursor.execute(
                "INSERT INTO certificates (student_name, course, issued_date, certificate_hash) VALUES (%s, %s, %s, %s)",
                (student_name, course, issued_date, certificate_hash)
            )
            certificate_id = cursor.lastrowid
            
            # Update certificate data with the actual ID
            certificate_data['certificate_id'] = certificate_id
            
            # Now create the blockchain block
            previous_hash = get_last_block_hash()
            timestamp = datetime.datetime.now()
            
            # Create block data string for hashing
            block_data_string = json.dumps(certificate_data) + previous_hash + timestamp.isoformat()
            current_hash = generate_hash(block_data_string)
            
            # Insert into blocks table
            cursor.execute(
                "INSERT INTO blocks (previous_hash, current_hash, timestamp, data) VALUES (%s, %s, %s, %s)",
                (previous_hash, current_hash, timestamp, json.dumps(certificate_data))
            )
            
            # Update certificate with the correct hash (should match block hash)
            cursor.execute(
                "UPDATE certificates SET certificate_hash = %s WHERE id = %s",
                (current_hash, certificate_id)
            )
            
            conn.commit()
            
            flash(f'Certificate created successfully! Certificate ID: {certificate_id}', 'success')
            return redirect(url_for('create_cert.homepage'))
            
        except Exception as e:
            conn.rollback()
            flash(f'Error creating certificate: {str(e)}', 'error')
            return render_template('homepage.html')
        finally:
            close_connection(conn)
    
    # GET request - redirect to homepage
    return redirect(url_for('create_cert.homepage'))

@create_cert_bp.route('/verify_certificate', methods=['GET', 'POST'])
def verify_certificate():
    """Verify a certificate's authenticity using blockchain"""
    
    if request.method == 'POST':
        # Check if it's an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return api_verify_certificate()
        
        # Original form submission logic (for non-JS browsers)
        certificate_hash = request.form.get('certificate_hash')
        certificate_id = request.form.get('certificate_id')
        
        if not certificate_hash and not certificate_id:
            flash('Please provide either Certificate Hash or Certificate ID', 'error')
            return render_template('verify_certificate.html')
        
        conn = create_connection()
        cursor = conn.cursor()
        
        try:
            # Search for certificate by hash or ID
            if certificate_hash:
                cursor.execute("""
                    SELECT c.*, b.previous_hash, b.timestamp as block_timestamp 
                    FROM certificates c 
                    JOIN blocks b ON c.certificate_hash = b.current_hash 
                    WHERE c.certificate_hash = %s
                """, (certificate_hash,))
            else:
                cursor.execute("""
                    SELECT c.*, b.previous_hash, b.timestamp as block_timestamp 
                    FROM certificates c 
                    JOIN blocks b ON c.certificate_hash = b.current_hash 
                    WHERE c.id = %s
                """, (certificate_id,))
            
            certificate = cursor.fetchone()
            
            if certificate:
                # Verify blockchain integrity
                cursor.execute("""
                    SELECT COUNT(*) as chain_length 
                    FROM blocks 
                    WHERE previous_hash != '0'
                """)
                chain_info = cursor.fetchone()
                
                # === FIXED LINKAGE VERIFICATION ===
                cursor.execute("""
                    SELECT previous_hash, current_hash 
                    FROM blocks 
                    WHERE current_hash = %s
                """, (certificate[4],))
                
                current_block = cursor.fetchone()
                
                if current_block:
                    previous_hash = current_block[0]
                    current_hash = current_block[1]
                    
                    if previous_hash == '0':
                        # Genesis block - always properly linked
                        is_linked = True
                    else:
                        # Check if another block points to this one
                        cursor.execute("""
                            SELECT COUNT(*) 
                            FROM blocks 
                            WHERE previous_hash = %s
                        """, (current_hash,))
                        linkage_count = cursor.fetchone()[0]
                        is_linked = linkage_count > 0
                else:
                    is_linked = False
                # === END FIX ===
                
                cert_dict = {
                    'id': certificate[0],
                    'student_name': certificate[1],
                    'course': certificate[2],
                    'issued_date': certificate[3].strftime('%Y-%m-%d %H:%M:%S') if certificate[3] else 'N/A',
                    'certificate_hash': certificate[4],
                    'previous_hash': certificate[5],
                    'block_timestamp': certificate[6].strftime('%Y-%m-%d %H:%M:%S') if certificate[6] else 'N/A',
                    'is_valid': True,
                    'chain_length': chain_info[0] if chain_info else 0,
                    'is_linked': is_linked  # Now this will be accurate!
                }
                
                flash('Certificate verified successfully!', 'success')
                return render_template('verify_certificate.html', certificate=cert_dict)
            else:
                flash('Certificate not found in the blockchain', 'error')
                return render_template('verify_certificate.html')
                
        except Exception as e:
            flash(f'Error verifying certificate: {str(e)}', 'error')
            return render_template('verify_certificate.html')
        finally:
            close_connection(conn)
    
    # GET request - show verification form
    return render_template('verify_certificate.html')

def api_verify_certificate():
    """API endpoint for AJAX certificate verification"""
    if request.is_json:
        data = request.get_json()
        certificate_hash = data.get('certificate_hash')
        certificate_id = data.get('certificate_id')
    else:
        certificate_hash = request.form.get('certificate_hash')
        certificate_id = request.form.get('certificate_id')
    
    if not certificate_hash and not certificate_id:
        return jsonify({
            'success': False,
            'message': 'Please provide either Certificate Hash or Certificate ID'
        })
    
    conn = create_connection()
    cursor = conn.cursor()
    
    try:
        # Search for certificate by hash or ID
        if certificate_hash:
            cursor.execute("""
                SELECT c.*, b.previous_hash, b.timestamp as block_timestamp 
                FROM certificates c 
                JOIN blocks b ON c.certificate_hash = b.current_hash 
                WHERE c.certificate_hash = %s
            """, (certificate_hash,))
        else:
            cursor.execute("""
                SELECT c.*, b.previous_hash, b.timestamp as block_timestamp 
                FROM certificates c 
                JOIN blocks b ON c.certificate_hash = b.current_hash 
                WHERE c.id = %s
            """, (certificate_id,))
        
        certificate = cursor.fetchone()
        
        if certificate:
            # Verify blockchain integrity
            cursor.execute("""
                SELECT COUNT(*) as chain_length 
                FROM blocks 
                WHERE previous_hash != '0'
            """)
            chain_info = cursor.fetchone()
            
            # === FIXED LINKAGE VERIFICATION ===
            cursor.execute("""
                SELECT previous_hash, current_hash 
                FROM blocks 
                WHERE current_hash = %s
            """, (certificate[4],))
            
            current_block = cursor.fetchone()
            
            if current_block:
                previous_hash = current_block[0]
                current_hash = current_block[1]
                
                if previous_hash == '0':
                    # Genesis block - always properly linked
                    is_linked = True
                else:
                    # Check if another block points to this one
                    cursor.execute("""
                        SELECT COUNT(*) 
                        FROM blocks 
                        WHERE previous_hash = %s
                    """, (current_hash,))
                    linkage_count = cursor.fetchone()[0]
                    is_linked = linkage_count > 0
            else:
                is_linked = False
            # === END FIX ===
            
            cert_dict = {
                'id': certificate[0],
                'student_name': certificate[1],
                'course': certificate[2],
                'issued_date': certificate[3].strftime('%Y-%m-%d %H:%M:%S') if certificate[3] else 'N/A',
                'certificate_hash': certificate[4],
                'previous_hash': certificate[5],
                'block_timestamp': certificate[6].strftime('%Y-%m-%d %H:%M:%S') if certificate[6] else 'N/A',
                'is_valid': True,
                'chain_length': chain_info[0] if chain_info else 0,
                'is_linked': is_linked  # Now this will be accurate!
            }
            
            return jsonify({
                'success': True,
                'certificate': cert_dict,
                'message': 'Certificate verified successfully!'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Certificate not found in the blockchain'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error verifying certificate: {str(e)}'
        })
    finally:
        close_connection(conn)

@create_cert_bp.route('/view_certificate')
def view_certificate():
    """Display all certificates"""
    conn = create_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT c.id, c.student_name, c.course, c.issued_date, c.certificate_hash
            FROM certificates c
            ORDER BY c.issued_date DESC
        """)
        
        certificates = cursor.fetchall()
        
        # Convert to list of dictionaries
        cert_list = []
        for cert in certificates:
            cert_list.append({
                'id': cert[0],
                'student_name': cert[1],
                'course': cert[2],
                'issued_date': cert[3],
                'certificate_hash': cert[4]
            })
        
        return render_template('view_certificate.html', certificates=cert_list)
        
    except Exception as e:
        flash(f'Error retrieving certificates: {str(e)}', 'error')
        return render_template('view_certificate.html', certificates=[])
    finally:
        close_connection(conn)