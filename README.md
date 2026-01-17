'''
# SkinTwin Cognitive Alchemist Workbench - Platform Integrations

This project provides a unified integration layer for connecting the **Amazing Salon App** with various third-party platforms, including Wix Appointment Bookings, OpenCart, and the Shopify B2B ecosystem. It serves as a central nervous system for the SkinTwin Cognitive Alchemist Workbench, enabling seamless data synchronization and workflow automation across multiple beauty-tech services.

## Key Features

*   **Unified API Gateway**: A single entry point to manage all platform integrations, abstracting away the complexities of individual APIs.
*   **Modular Connectors**: Extensible connectors for each platform (Wix, OpenCart, Shopify) that handle authentication, data mapping, and API interactions.
*   **Cross-Platform Data Models**: A canonical data model for appointments, clients, products, and orders, enabling consistent data representation across all platforms.
*   **B2B E-commerce Support**: Specialized integration with Shopify's B2B features, including companies, catalogs, and draft orders.
*   **Webhook Handling**: A robust webhook router to process real-time events from all platforms, with a unified event system for cross-platform workflows.
*   **Data Synchronization**: Tools for synchronizing appointments, clients, and products between the local application and external platforms.
*   **Configuration-Driven**: Simple JSON-based configuration for enabling and managing platform integrations.

## Project Structure

```
/home/ubuntu/skintwin-integrations/
├── AmazingSalonApp9ragbot3/
│   ├── integrations/
│   │   ├── __init__.py             # Main integration package
│   │   ├── gateway.py              # Unified API gateway
│   │   ├── webhook_router.py       # Unified webhook router
│   │   ├── common/                 # Common components
│   │   │   ├── __init__.py
│   │   │   ├── base_connector.py   # Base connector class
│   │   │   ├── exceptions.py       # Custom exceptions
│   │   │   └── models.py           # Unified data models
│   │   ├── wix/                    # Wix Bookings integration
│   │   │   ├── __init__.py
│   │   │   ├── connector.py
│   │   │   ├── webhooks.py
│   │   │   └── models.py
│   │   ├── opencart/               # OpenCart integration
│   │   │   ├── __init__.py
│   │   │   ├── connector.py
│   │   │   ├── webhooks.py
│   │   │   └── models.py
│   │   └── shopify/                # Shopify B2B integration
│   │       ├── __init__.py
│   │       ├── connector.py
│   │       ├── webhooks.py
│   │       └── models.py
│   ├── main.py                     # Main application entry point
│   ├── app.py                      # Flask application setup
│   ├── models.py                   # Application data models
│   └── ...
├── config.example.json             # Example configuration file
└── README.md                       # This file
```

## Getting Started

### 1. Installation

Clone the repository and install the required dependencies:

```bash
# Clone the repository
git clone https://github.com/skintwin-ai/skintwin-integrations.git
cd skintwin-integrations

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Create a `config.json` file by copying the `config.example.json` file and filling in your platform credentials:

```bash
cp config.example.json config.json
```

Edit `config.json` with your API keys, site IDs, and other required information for each platform you want to enable.

### 3. Running the Application

Run the main application, which will start the Flask server and initialize the integration gateway:

```bash
python main.py
```

The application will be available at `http://localhost:5000` by default.

## Usage

### API Gateway

The integration gateway provides a set of API endpoints for interacting with the integrated platforms. These endpoints are available under the `/api/integrations/` prefix.

*   `/api/integrations/health`: Check the health of the gateway and all connectors.
*   `/api/integrations/test-connections`: Test the connection to each enabled platform.
*   `/api/integrations/appointments/sync`: Synchronize appointments from all platforms.
*   `/api/integrations/clients/sync`: Synchronize clients from all platforms.
*   `/api/integrations/products/sync`: Synchronize products from all platforms.
*   `/api/integrations/b2b/companies`: Get a list of B2B companies from Shopify.

### Webhooks

The application exposes webhook endpoints to receive real-time events from the integrated platforms. These endpoints are available under the `/webhooks/` prefix.

*   `/webhooks/wix`: Handles webhooks from Wix.
*   `/webhooks/opencart`: Handles webhooks from OpenCart.
*   `/webhooks/shopify`: Handles webhooks from Shopify.

When an event is received, the webhook router processes it and emits a unified event that can be used to trigger cross-platform workflows.

## Documentation

For more detailed information on the integration architecture, data models, and API usage, please refer to the [Integration Architecture Documentation](documentation.md).

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue to discuss any changes.

## License

This project is licensed under the MIT License. See the `LICENSE` file for more details.
'''
