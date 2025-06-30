import random
from datetime import datetime, timedelta
from app import db, User, generate_password_hash, app

offres = ['essentiel', 'pro', 'sur-mesure']
statuts = ['payé', 'en_attente_validation', 'annulé', 'preuve_supplémentaire']

def random_date_this_year():
    now = datetime.now()
    start = datetime(now.year, 1, 1)
    return start + timedelta(days=random.randint(0, (now - start).days))

def create_fake_users(n=30):
    for i in range(n):
        email = f"fake{i}@test.com"
        password_hash = generate_password_hash('test1234')
        offre = random.choice(offres)
        statut = random.choices(statuts, weights=[0.5,0.3,0.1,0.1])[0]
        date_inscription = random_date_this_year()
        user = User(email=email, password_hash=password_hash, offre=offre, statut=statut, date_inscription=date_inscription)
        db.session.add(user)
    db.session.commit()
    print(f"{n} utilisateurs de test créés !")

if __name__ == '__main__':
    with app.app_context():
        create_fake_users(200) 