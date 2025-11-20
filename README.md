# Tasty Corner Restaurant. 

A Flask-based restaurant website with user authentication, menu ordering, allergy tracking, tip selection, and order management.

## Features

- **User Authentication**: Sign up and sign in for customers
- **Menu System**: Browse and order from the restaurant menu
- **Allergy Tracking**: Specify allergies when adding items to cart
- **Tip Selection**: Choose from preset tips (2%, 5%, 10%, 20%), custom amount, or no tip
- **Delivery & Taxes**: Automatic calculation of delivery fees and Louisiana taxes
- **Order Management**: Save orders to CSV (can be migrated to SQL later)
- **Stripe Integration**: Placeholder for future Stripe payment integration

## Installation

1. Install Python 3.8 or higher
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Application

1. Start the Flask server:
```bash
python app.py
```

2. Open your browser and navigate to:
```
http://localhost:5000
```

## Project Structure

```
.
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── data/                 # CSV data files (created automatically)
│   ├── users.csv         # User accounts
│   ├── orders.csv        # Order history
│   └── menu.csv          # Menu items
├── templates/            # HTML templates
│   ├── base.html
│   ├── index.html
│   ├── signup.html
│   ├── signin.html
│   ├── menu.html
│   ├── cart.html
│   ├── checkout.html
│   └── order_confirmation.html
└── static/               # Static files
    ├── style.css         # Main stylesheet
    └── images/           # Menu item images
```

## Configuration

- **Tax Rate**: Currently set to 9.45% (Louisiana state + local average)
- **Delivery Fee**: $5.99
- **Secret Key**: Change the `app.secret_key` in `app.py` for production!

## Adding Menu Items

Menu items are stored in `data/menu.csv`. You can:
1. Edit the CSV file directly
2. Add items programmatically through the admin panel (future feature)

Format: `item_id, name, description, price, category, image`

## Adding Images

Place your menu item images in `static/images/` directory. The images will be automatically loaded based on the filename in the menu CSV.

## Future Enhancements

- Admin panel for managing menu, orders, and users
- Worker dashboard for kitchen staff
- Delivery driver interface
- SQL database migration
- Real Stripe payment integration
- Order tracking
- Email notifications

## Notes

- Data is stored in CSV files for simplicity (easy to migrate to SQL later)
- All passwords are hashed using Werkzeug's security functions
- The application uses sessions for user authentication
- Louisiana tax rate is approximate; adjust as needed

## License

Educational purposes.

