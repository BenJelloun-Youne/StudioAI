from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import os
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime

app = Flask(__name__)
app.secret_key = "ma_cle_ultra_secrete_2024"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///AIPIflow.db'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    statut = db.Column(db.String(32), default='gratuit')
    offre = db.Column(db.String(32), default='essentiel')
    date_inscription = db.Column(db.DateTime, server_default=db.func.now())
    is_admin = db.Column(db.Boolean, default=False)
    preuve_paiement = db.Column(db.String(256), nullable=True)
    message_admin = db.Column(db.String(512), nullable=True)

class AgentIA(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    type = db.Column(db.String(64))  # 'emailing', 'comptable'
    nom = db.Column(db.String(128))
    config = db.Column(db.Text)
    user = db.relationship('User', backref=db.backref('agents', lazy=True))

def create_db():
    with app.app_context():
        db.create_all()
        # Création du compte admin par défaut
        if not User.query.filter_by(email='admin@AIPIflow.com').first():
            admin = User(email='admin@AIPIflow.com', password_hash=generate_password_hash('admin123'), is_admin=True, statut='payé', offre='pro')
            db.session.add(admin)
            db.session.commit()

create_db()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/contact', methods=['POST'])
def contact():
    name = request.form.get('name')
    email = request.form.get('email')
    message = request.form.get('message')
    # Stockage local du message
    with open('contact_messages.txt', 'a', encoding='utf-8') as f:
        f.write(f"Nom: {name}\nEmail: {email}\nMessage: {message}\n---\n")
    flash('Merci pour votre message ! Nous vous répondrons très vite. Shukran!')
    return redirect(url_for('home'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            flash('Bienvenue !')
            if user.is_admin:
                return redirect(url_for('admin'))
            return redirect(url_for('dashboard'))
        else:
            flash('Email ou mot de passe incorrect.')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        offre = request.form.get('offre', 'essentiel')
        if User.query.filter_by(email=email).first():
            flash('Cet email existe déjà.')
            return redirect(url_for('register'))
        user = User(email=email, password_hash=generate_password_hash(password), offre=offre)
        db.session.add(user)
        db.session.commit()
        flash('Compte créé, connectez-vous !')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Déconnecté.')
    return redirect(url_for('home'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    return render_template('dashboard.html', user=user)

@app.route('/paiement', methods=['GET', 'POST'])
def paiement():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if request.method == 'POST':
        mode = request.form.get('mode')
        preuve = request.form.get('preuve')
        file = request.files.get('file')
        if file and file.filename:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            user.preuve_paiement = filepath
        elif preuve:
            user.preuve_paiement = preuve
        user.statut = 'en_attente_validation'
        db.session.commit()
        flash('Votre demande de paiement a été prise en compte. Nous vous contacterons pour valider.')
        return redirect(url_for('dashboard'))
    return render_template('paiement.html', user=user)

@app.route('/admin')
def admin():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user.is_admin:
        flash("Accès réservé à l'admin.")
        return redirect(url_for('dashboard'))
    users = User.query.filter(User.email != 'admin@AIPIflow.com').all()
    # Stats
    now = datetime.now()
    abonnements_actifs = User.query.filter(User.statut == 'payé', User.email != 'admin@AIPIflow.com').count()
    inscriptions_mois = User.query.filter(db.extract('month', User.date_inscription) == now.month, db.extract('year', User.date_inscription) == now.year, User.email != 'admin@AIPIflow.com').count()
    paiements_en_attente = User.query.filter(User.statut == 'en_attente_validation', User.email != 'admin@AIPIflow.com').count()
    # CA et MRR (selon offre)
    offre_prix = {'essentiel': 1200, 'pro': 3300, 'sur-mesure': 0}
    users_payes = User.query.filter(User.statut == 'payé', User.email != 'admin@AIPIflow.com').all()
    ca_mois = sum(offre_prix.get(u.offre, 0) for u in users_payes if u.date_inscription.month == now.month and u.date_inscription.year == now.year)
    mrr = sum(offre_prix.get(u.offre, 0) for u in users_payes)
    return render_template('admin.html', users=users, abonnements_actifs=abonnements_actifs, inscriptions_mois=inscriptions_mois, paiements_en_attente=paiements_en_attente, ca_mois=ca_mois, mrr=mrr)

@app.route('/admin/valider/<int:user_id>')
def valider_paiement(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user.is_admin:
        flash("Accès réservé à l'admin.")
        return redirect(url_for('dashboard'))
    u = User.query.get(user_id)
    if u:
        u.statut = 'payé'
        u.message_admin = 'Votre paiement a été validé. Merci !'
        db.session.commit()
        flash('Paiement validé pour ' + u.email)
    return redirect(url_for('admin'))

@app.route('/admin/annuler/<int:user_id>')
def annuler_paiement(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user.is_admin:
        flash("Accès réservé à l'admin.")
        return redirect(url_for('dashboard'))
    u = User.query.get(user_id)
    if u:
        u.statut = 'annulé'
        u.message_admin = 'Votre paiement a été refusé. Merci de nous contacter.'
        db.session.commit()
        flash('Paiement annulé pour ' + u.email)
    return redirect(url_for('admin'))

@app.route('/admin/preuve/<int:user_id>', methods=['POST'])
def demander_preuve(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user.is_admin:
        flash("Accès réservé à l'admin.")
        return redirect(url_for('dashboard'))
    u = User.query.get(user_id)
    if u:
        u.statut = 'preuve_supplémentaire'
        u.message_admin = request.form.get('message_admin', 'Merci de fournir une preuve de paiement supplémentaire.')
        db.session.commit()
        flash('Demande de preuve supplémentaire envoyée à ' + u.email)
    return redirect(url_for('admin'))

@app.route('/admin/message/<int:user_id>', methods=['POST'])
def admin_message(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user.is_admin:
        flash("Accès réservé à l'admin.")
        return redirect(url_for('dashboard'))
    u = User.query.get(user_id)
    if u:
        u.message_admin = request.form.get('message_admin', '')
        db.session.commit()
        flash('Message envoyé à ' + u.email)
    return redirect(url_for('admin'))

@app.route('/admin/kpi-data')
def admin_kpi_data():
    now = datetime.now()
    labels = []
    inscriptions = []
    ca = []
    offre_prix = {'essentiel': 1200, 'pro': 3300, 'sur-mesure': 0}
    for i in range(5, -1, -1):
        month = (now.month - i - 1) % 12 + 1
        year = now.year if now.month - i > 0 else now.year - 1
        label = f"{month:02d}/{year}"
        labels.append(label)
        users_month = User.query.filter(db.extract('month', User.date_inscription) == month, db.extract('year', User.date_inscription) == year, User.email != 'admin@AIPIflow.com').all()
        inscriptions.append(len(users_month))
        ca.append(sum(offre_prix.get(u.offre, 0) for u in users_month if u.statut == 'payé'))
    return jsonify({'labels': labels, 'inscriptions': inscriptions, 'ca': ca})

@app.route('/admin/agents/<int:user_id>')
def admin_agents(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user.is_admin:
        flash("Accès réservé à l'admin.")
        return redirect(url_for('dashboard'))
    target_user = User.query.get(user_id)
    agents = AgentIA.query.filter_by(user_id=user_id).all()
    return render_template('admin_agents.html', user=target_user, agents=agents)

@app.route('/admin/agents/add/<int:user_id>', methods=['GET', 'POST'])
def add_agent(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user.is_admin:
        flash("Accès réservé à l'admin.")
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        nom = request.form['nom']
        type_agent = request.form['type']
        config = request.form.get('config', '')
        agent = AgentIA(user_id=user_id, nom=nom, type=type_agent, config=config)
        db.session.add(agent)
        db.session.commit()
        flash('Agent IA créé avec succès.')
        return redirect(url_for('admin_agents', user_id=user_id))
    return render_template('add_agent.html', user_id=user_id)

@app.route('/admin/agents/delete/<int:agent_id>/<int:user_id>', methods=['POST'])
def delete_agent(agent_id, user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user.is_admin:
        flash("Accès réservé à l'admin.")
        return redirect(url_for('dashboard'))
    agent = AgentIA.query.get(agent_id)
    if agent:
        db.session.delete(agent)
        db.session.commit()
        flash('Agent IA supprimé.')
    return redirect(url_for('admin_agents', user_id=user_id))

@app.route('/mes-agents')
def mes_agents():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if user.statut != 'payé':
        flash("Accès réservé aux utilisateurs ayant payé.")
        return redirect(url_for('dashboard'))
    agents = AgentIA.query.filter_by(user_id=user.id).all()
    return render_template('mes_agents.html', user=user, agents=agents)

@app.route('/mes-agents/config/<int:agent_id>', methods=['GET', 'POST'])
def config_agent(agent_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    agent = AgentIA.query.get(agent_id)
    if not agent or agent.user_id != user.id:
        flash("Accès refusé.")
        return redirect(url_for('mes_agents'))
    if user.statut != 'payé':
        flash("Accès réservé aux utilisateurs ayant payé.")
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        # On stocke la config personnalisée selon le type d'agent
        if agent.type == 'emailing':
            config = {
                'email': request.form.get('email', ''),
                'objet': request.form.get('objet', ''),
                'template': request.form.get('template', '')
            }
        elif agent.type == 'comptable':
            config = {
                'logiciel': request.form.get('logiciel', ''),
                'frequence': request.form.get('frequence', ''),
                'notes': request.form.get('notes', '')
            }
        else:
            config = {}
        import json
        agent.config = json.dumps(config)
        db.session.commit()
        flash('Configuration enregistrée !')
        return redirect(url_for('mes_agents'))
    # Pré-remplir le formulaire si config existe
    import json
    config = json.loads(agent.config) if agent.config else {}
    return render_template('config_agent.html', agent=agent, config=config)

# --- SCRIPT POUR AJOUTER DES UTILISATEURS FACTICES ---
def creer_utilisateurs_fictifs(nb=20):
    from random import choice, randint
    from faker import Faker
    fake = Faker('fr_FR')
    offres = ['essentiel', 'pro', 'sur-mesure']
    statuts = ['payé', 'en_attente_validation', 'annulé', 'preuve_supplémentaire']
    with app.app_context():
        for i in range(nb):
            email = fake.unique.email()
            password_hash = generate_password_hash('test1234')
            offre = choice(offres)
            statut = choice(statuts)
            date_inscription = fake.date_time_between(start_date='-6M', end_date='now')
            if not User.query.filter_by(email=email).first():
                user = User(
                    email=email,
                    password_hash=password_hash,
                    offre=offre,
                    statut=statut,
                    date_inscription=date_inscription,
                    is_admin=False
                )
                db.session.add(user)
        db.session.commit()
    print(f"{nb} utilisateurs fictifs créés !")

def creer_agents_ia_fictifs(nb_agents_par_user=2):
    from random import choice, randint
    from faker import Faker
    import json
    fake = Faker('fr_FR')
    types_agents = ['emailing', 'comptable']
    with app.app_context():
        users = User.query.filter(User.email != 'admin@AIPIflow.com').all()
        total = 0
        for user in users:
            for _ in range(nb_agents_par_user):
                type_agent = choice(types_agents)
                if type_agent == 'emailing':
                    config = {
                        'email': fake.email(),
                        'objet': fake.sentence(nb_words=6),
                        'template': fake.text(max_nb_chars=100)
                    }
                else:
                    config = {
                        'logiciel': choice(['Sage', 'Cegid', 'Quickbooks', 'EBP']),
                        'frequence': choice(['mensuel', 'trimestriel', 'annuel']),
                        'notes': fake.sentence(nb_words=10)
                    }
                agent = AgentIA(
                    user_id=user.id,
                    type=type_agent,
                    nom=fake.first_name() + 'Bot',
                    config=json.dumps(config)
                )
                db.session.add(agent)
                total += 1
        db.session.commit()
    print(f"{total} agents IA fictifs créés !")

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'fakes':
        try:
            nb = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        except ValueError:
            nb = 20
        creer_utilisateurs_fictifs(nb)
    elif len(sys.argv) > 1 and sys.argv[1] == 'fakes_agents':
        try:
            nb_agents = int(sys.argv[2]) if len(sys.argv) > 2 else 2
        except ValueError:
            nb_agents = 2
        creer_agents_ia_fictifs(nb_agents)
    elif len(sys.argv) > 1 and sys.argv[1] == 'list_users':
        from tabulate import tabulate
        with app.app_context():
            users = User.query.filter(User.email != 'admin@AIPIflow.com').limit(30).all()
            print(tabulate([[u.id, u.email, u.statut, u.offre, u.date_inscription.strftime('%Y-%m-%d')] for u in users], headers=['ID','Email','Statut','Offre','Date']))
    elif len(sys.argv) > 1 and sys.argv[1] == 'export_users_csv':
        import csv
        with app.app_context():
            users = User.query.filter(User.email != 'admin@AIPIflow.com').all()
            with open('utilisateurs_export.csv', 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['ID', 'Email', 'Statut', 'Offre', 'Date'])
                for u in users:
                    writer.writerow([u.id, u.email, u.statut, u.offre, u.date_inscription.strftime('%Y-%m-%d')])
            print(f"Export CSV terminé : utilisateurs_export.csv ({len(users)} utilisateurs)")
    else:
        app.run(debug=True)
