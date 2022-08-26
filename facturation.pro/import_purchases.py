import csv
import os
import requests
import datetime
import json
import re
import sys

FILE = 'file.csv'
LIMIT = 0

load_to_api = True if len(sys.argv) > 1 and sys.argv[1] == 'load' else False

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

FIRM_ID = "[YOUR_FIRM_ID]"
ID = "[YOUR_API_AD]"
KEY = "[YOUR_API_KEY]"

# Compléter avec les libellés présents sur votre revelé bancaire, le 2ème paramètre active le calcul de la TVA
categories_dict = {
    "Restaurant" : (('FLUNCH', 'SUSHI SHOP'), False),
    "Carburant" : (('ESSO', 'TOTAL'), False),
    "Fourniture" : (('FNAC', 'LDLC', 'MICROSOFT','APPLE.COM/FR'), True),
    "Formation" : (('UDEMY',), True),
}

__location__ = os.path.realpath(
    os.path.join(os.getcwd(), os.path.dirname(__file__)))

def set_suppliers():
    response = session.get(f'https://www.facturation.pro/firms/{FIRM_ID}/suppliers.json')
    global suppliers
    suppliers = json.loads(response.content)

# Modifier selon les intitulés de votre banque
def get_payment_mode(title):
    if title.startswith("PAIEMENT CB") or title.startswith("PAIEMENT PSC"):
        return 2
    elif title.startswith("VIR"):
        return 3
    elif title.startswith("PRLV"):
        return 8
    else:
        print(f'{bcolors.WARNING}[WARNING] Le mode de paiement n\'a pas été trouvé pour {title}{bcolors.ENDC}')
    return None

def calculate_vat_amount(total_with_vat):
    vat_amount = (float(total_with_vat.replace(',','.')) / 120) * 20
    vat_amount = round(vat_amount, 2)
    vat_amount = str(vat_amount).replace('.',',')
    return vat_amount

def get_supplier_infos(title, dictionnary):
    for cat in dictionnary:
        contained = [x for x in dictionnary[cat][0] if x in title]
        if contained:
            # Supplier name
            supplier_name = cat
            # Title alias
            title_alias = contained[0]
            # TVA
            is_tva = dictionnary[cat][1]
            print('supplier:', supplier_name, ', title_alias:', title_alias, ', is_tva:', str(is_tva))
            return supplier_name, title_alias, is_tva
        else:
            continue
    return None, None, None

def get_supplier_id(supplier):
    for s in suppliers:
        if supplier.upper() in s['company_name'].upper():
            return s['id']
    return None

# @TODO LA FONCTION DOIT AUSSI DEMANDER UN TITLE_ALIAS, ET DOIT DETERMINER LA TVA
def ask_for_supplier(categories_dict):
    print(f'{bcolors.WARNING}[WARNING] La catégorie n\'a pas été trouvée pour {title}{bcolors.ENDC}')
    i = 0
    list_categories = list(categories_dict.keys())
    for k in list_categories:
        print(k, ':', i)
        i += 1
    while True:
        id = input("Définir catégorie (ou ENTER pour passer) : ")
        id = int(id) if id != '' else id
        if id == "":
            print(f'{bcolors.WARNING}[WARNING] Ligne non prise en compte{bcolors.ENDC}')
            return None
        elif (id in range (0, len(list_categories))):
            print('ok')
            return list_categories[id]
        else:
            return ask_for_supplier(categories_dict)

# Non implémenté
def purchase_exists(session, paid_on, supplier, total_with_vat):
    return False

def import_via_api(session, paid_on, invoiced_on, title_alias, total_with_vat, vat_amount, payment_mode, supplier_id):
    
    if not load_to_api:
        return
    try:
        response = session.post(f'https://www.facturation.pro/firms/{FIRM_ID}/purchases.json', json = {
            "supplier_id": supplier_id, 
            "invoiced_on": invoiced_on,
            "paid_on": paid_on,
            "payment_mode": payment_mode,
            "title": title_alias,
            "total_with_vat": total_with_vat,
            "vat_amount": vat_amount
            })

        return response.json()
        
    except requests.exceptions.ConnectionError:
        print(f'{bcolors.FAIL}[ERREUR] API Facturation non joignable !{bcolors.ENDC}')
        quit()
    
###########################################################################################################################

# Préparation des requêtes API
session = requests.Session()
session.auth = (ID, KEY)
session.headers.update({
    'User-Agent': 'MonApp (contact@mon-domaine.com)',
    'Content-Type': 'application/json; charset=utf-8',
})

set_suppliers()

nb_lines = 0
nb_envois = 0
nb_tva = 0

try:
    # Lecture du fichier source
    csvfile =  open(os.path.join(__location__, FILE), newline='')
    file = csv.reader(csvfile, delimiter=';', quotechar='|')

    # On saute les en-têtes
    next(file)

    for row in file:
        # ROW => [0] Date, [1] Date valeur, [2] Débit, [3] Crédit,  [4] Libellé,  [5] Solde

        # Si pas de débit, on passe à la ligne suivante
        if row[2] == '':
            continue
        nb_lines += 1
        
        # PAID_ON, INVOICED_ON : convertir la date au format attendu
        paid_on = invoiced_on = datetime.datetime.strptime(row[1], '%d/%m/%Y').strftime('%Y-%m-%d')

        # TOTAL_WITH_VAT : convertir en valeur absolue le montant
        total_with_vat = row[2].lstrip('-')

        # TITLE : retirer les espaces en trop
        title = re.sub(" +", " ", row[4])

        print(f'\n{bcolors.HEADER}[INFO] {paid_on} - {title} {total_with_vat} euros{bcolors.ENDC}')

        # PAYMENT_MODE
        payment_mode = get_payment_mode(title)

        # SUPPLIER, TVA
        supplier, title_alias, is_tva = get_supplier_infos(title, categories_dict)

        if supplier:
            supplier_id = get_supplier_id(supplier)
        else:
            continue
        
        # TVA AMOUNT
        if is_tva:
            vat_amount = calculate_vat_amount(total_with_vat)
            print(f'{bcolors.OKBLUE}[INFO] TVA appliquée, penser à saisir le numéro de facture{bcolors.ENDC}')
            nb_tva += 1
        else:
            vat_amount = total_with_vat

        # Création via API
        if payment_mode and supplier:
            if not purchase_exists(session, paid_on, supplier, total_with_vat):
                api_return = import_via_api(session, paid_on, invoiced_on, title_alias, total_with_vat, vat_amount, payment_mode, supplier_id)
                nb_envois += 1
                print(f'{bcolors.OKGREEN}[SUCCESS] OK !{bcolors.ENDC}')
            else:
                print(f'{bcolors.FAIL}[INFO] Failed !{bcolors.ENDC}')
        if LIMIT != 0 and nb_envois >= LIMIT:
            break


except FileNotFoundError:
    print(f'{bcolors.FAIL}[ERREUR] Fichier file.csv absent !{bcolors.ENDC}')
    quit()

finally:
   csvfile.close()

print(f'{bcolors.WARNING}---{bcolors.ENDC}')
print()
if load_to_api:
    print(f'{bcolors.WARNING}[!] --- IMPORT API ACTIF ---{bcolors.ENDC}')
else:
    print(f'{bcolors.OKBLUE}[*] IMPORT API INACTIF{bcolors.ENDC}')
print(f'{bcolors.OKBLUE}[*]{bcolors.ENDC} Nombre de lignes dans le fichier initial :{bcolors.BOLD}', nb_lines, f'{bcolors.ENDC}')
print(f'{bcolors.OKBLUE}[*]{bcolors.ENDC} Nombre de lignes créées avec succès :{bcolors.BOLD}', nb_envois, f'{bcolors.ENDC}')
print(f'{bcolors.OKBLUE}[*]{bcolors.ENDC} Nombre de lignes avec TVA appliquée :{bcolors.BOLD}', nb_tva, f'{bcolors.ENDC}')
