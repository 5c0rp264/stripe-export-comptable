# Stripe Comptable Export

Outil d'export des données comptables Stripe pour justification auprès d'un comptable français.

## 📋 Description

Ce script Python permet d'extraire toutes les informations comptables associées à un virement Stripe (payout) et de les exporter dans des formats exploitables par un comptable français :

- **CSV** : Fichiers avec séparateur point-virgule et format numérique français
- **Excel** : Classeur avec plusieurs onglets (Résumé, Transactions, Factures, Frais)
- **PDF** : Rapport comptable synthétique
- **Factures PDF** : Téléchargement automatique des factures Stripe

### Données exportées

Pour chaque virement, l'outil récupère :

- ✅ Transactions (balance transactions)
- ✅ Paiements (charges)
- ✅ Remboursements (refunds)
- ✅ Factures (invoices) avec PDF
- ✅ Frais Stripe détaillés
- ✅ Litiges (disputes)

## 🚀 Installation

### Prérequis

- Python 3.9 ou supérieur
- Un compte Stripe avec une clé API

### Étapes

1. **Cloner le dépôt**

```bash
git clone https://github.com/YOUR_USERNAME/stripe-export-comptable.git
cd stripe-export-comptable
```

2. **Créer un environnement virtuel**

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# ou
venv\Scripts\activate  # Windows
```

3. **Installer les dépendances**

```bash
pip install -r requirements.txt
```

4. **Configurer les variables d'environnement**

Copiez le fichier `.env` vers `.env.local` et renseignez votre clé API Stripe :

```bash
cp .env .env.local
```

Éditez `.env.local` :

```env
STRIPE_API_KEY=sk_live_votre_cle_api_stripe
OUTPUT_DIR=./output
```

> ⚠️ **Important** : Le fichier `.env.local` est ignoré par Git et ne sera pas commité. Ne partagez jamais votre clé API !

## 📖 Utilisation

### Export d'un seul virement

```bash
python -m src.main --payout po_xxxxxxxxxxxxx
```

### Export de tous les virements sur une période

```bash
python -m src.main --from 2024-01-01 --to 2024-12-31
```

### Options disponibles

| Option | Description |
|--------|-------------|
| `-p, --payout` | ID du payout Stripe (ex: `po_xxxxx`) |
| `--from` | Date de début (format: `YYYY-MM-DD`) |
| `--to` | Date de fin (format: `YYYY-MM-DD`) |
| `-o, --output` | Répertoire de sortie (défaut: `./output`) |
| `--no-invoices` | Ne pas télécharger les factures PDF |
| `-k, --api-key` | Clé API Stripe (alternative à `.env.local`) |

### Exemples

```bash
# Export simple avec répertoire personnalisé
python -m src.main --payout po_xxxxx --output ./exports/2024

# Export d'une période sans télécharger les factures
python -m src.main --from 2024-01-01 --to 2024-03-31 --no-invoices

# Utilisation avec clé API en ligne de commande
python -m src.main --payout po_xxxxx --api-key sk_live_xxxxx
```

## 📁 Structure des exports

Chaque virement génère un dossier ZIP contenant :

```
payout_20241215_po_xxxxx/
├── resume.csv              # Récapitulatif du virement
├── transactions.csv        # Toutes les transactions
├── factures.csv           # Liste des factures
├── frais.csv              # Détail des frais Stripe
├── recap_payout.xlsx      # Classeur Excel complet
├── rapport_comptable.pdf  # Rapport PDF synthétique
└── factures/              # Factures PDF téléchargées
    ├── INV-0001.pdf
    ├── INV-0002.pdf
    └── ...
```

## 📊 Format des données

### Colonnes des transactions (CSV/Excel)

| Colonne | Description |
|---------|-------------|
| Date | Date de la transaction |
| Référence | ID Stripe de la transaction |
| Type | Type (Paiement, Remboursement, Frais, etc.) |
| Description | Description de la transaction |
| Montant Brut | Montant avant frais |
| Frais | Frais Stripe |
| Montant Net | Montant après frais |
| Devise | EUR, USD, etc. |
| Client | Nom ou email du client |
| N° Facture | Numéro de facture associé |

### Format numérique

Les montants sont formatés selon les conventions françaises :
- Séparateur décimal : virgule (`,`)
- Séparateur de milliers : espace
- Exemple : `1 234,56 €`

## 🔧 Développement

### Structure du projet

```
stripe-export-comptable/
├── .env                    # Template (commité)
├── .env.local             # Credentials (ignoré)
├── .gitignore
├── README.md
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py            # Point d'entrée CLI
│   ├── stripe_client.py   # Client API Stripe
│   ├── models.py          # Modèles de données
│   ├── utils.py           # Utilitaires
│   ├── invoice_downloader.py
│   └── exporters/
│       ├── __init__.py
│       ├── csv_exporter.py
│       ├── excel_exporter.py
│       └── pdf_exporter.py
└── output/                # Exports générés (ignoré)
```

### Dépendances principales

- `stripe` - SDK officiel Stripe
- `pandas` - Manipulation de données
- `openpyxl` - Export Excel
- `reportlab` - Génération PDF
- `click` - Interface CLI
- `python-dotenv` - Gestion des variables d'environnement

## 🔒 Sécurité

- Les clés API Stripe doivent être stockées dans `.env.local` (ignoré par Git)
- N'utilisez jamais de clé API en production dans le code source
- Utilisez de préférence des clés API restreintes avec uniquement les permissions nécessaires

### Permissions Stripe requises

L'API key doit avoir accès en lecture à :
- `Balance Transactions`
- `Charges`
- `Invoices`
- `Payouts`
- `Refunds`
- `Disputes`
- `Customers`

## 📄 Licence

MIT License - Voir le fichier LICENSE pour plus de détails.

## 🤝 Contribution

Les contributions sont les bienvenues ! N'hésitez pas à ouvrir une issue ou une pull request.

## 📞 Support

Pour toute question ou problème, ouvrez une issue sur GitHub.

