# Launch SUNO billing server (Stripe Checkout)
$ErrorActionPreference = 'Stop'

python -m pip install -r requirements.txt
python billing_server.py