'''
# SkinTwin Integrations - Technical Documentation

## 1. Introduction

This document provides a detailed technical overview of the SkinTwin Platform Integrations project. The goal of this project is to create a seamless, unified ecosystem for the **Amazing Salon App** by integrating with key third-party platforms: **Wix Appointment Bookings**, **OpenCart**, and the **Shopify B2B ecosystem**.

This integration layer serves as the central nervous system for the **SkinTwin Cognitive Alchemist Workbench**, enabling:

*   **Centralized Data Management**: Synchronize appointments, clients, products, and orders across all platforms.
*   **Automated Workflows**: Trigger cross-platform actions based on real-time events.
*   **Unified Business Logic**: Apply consistent business rules and logic across all sales and booking channels.
*   **Enhanced B2B Capabilities**: Leverage Shopify's powerful B2B features for wholesale and professional clients.

## 2. Architecture Overview

The integration architecture is designed to be modular, scalable, and easy to extend. It consists of three main components:

### 2.1. Unified API Gateway (`gateway.py`)

The **Integration Gateway** is the heart of the system. It provides a single, consistent REST API for the frontend application to interact with all integrated platforms. Its key responsibilities include:

*   **Connector Management**: Initializes and manages the lifecycle of all platform connectors.
*   **Request Routing**: Routes incoming API requests to the appropriate connector based on the target platform.
*   **Data Aggregation**: Fetches and aggregates data from multiple platforms for unified views.
*   **Cross-Platform Operations**: Orchestrates complex operations that span multiple platforms, such as creating a client on all systems simultaneously.

### 2.2. Platform Connectors

Each integrated platform has a dedicated **Connector** responsible for all communication with that platform's API. This modular design isolates platform-specific logic and makes it easy to add new integrations in the future.

*   **`WixBookingsConnector`**: Manages interactions with the Wix Bookings API for appointments and services.
*   **`OpenCartConnector`**: Handles communication with the OpenCart API for orders, products, and customers.
*   **`ShopifyB2BConnector`**: A specialized connector for the Shopify Admin API, with a focus on B2B features like companies, catalogs, and draft orders.

Each connector inherits from a `BaseConnector` class, which provides common functionality such as rate limiting, session management, and standardized error handling.

### 2.3. Unified Webhook Router (`webhook_router.py`)

The **Webhook Router** is responsible for processing incoming webhooks from all platforms. It provides a centralized, secure, and reliable way to handle real-time events.

*   **Webhook Verification**: Validates the authenticity of incoming webhooks using HMAC signatures and other security mechanisms.
*   **Event Routing**: Routes webhook payloads to the appropriate platform-specific handler.
*   **Unified Event System**: Maps platform-specific events to a canonical set of unified event types (e.g., `appointment.created`, `product.updated`). This allows the application to react to events in a platform-agnostic way.
*   **Event Listeners**: Allows different parts of the application to subscribe to unified events and trigger custom workflows.

## 3. Data Models (`common/models.py`)

To ensure data consistency across all platforms, we use a set of **unified data models**. These models represent the canonical structure for key business objects. Each connector is responsible for mapping data between these unified models and the platform-specific models.

*   **`UnifiedAppointment`**: Represents a booking or appointment.
*   **`UnifiedClient`**: Represents a customer or client.
*   **`UnifiedProduct`**: Represents a product or service.
*   **`UnifiedOrder`**: Represents an order or transaction.
*   **`PlatformReference`**: A special model used to track the external ID of an object on each platform, enabling cross-platform synchronization.

## 4. Configuration (`config.example.json`)

The entire integration system is driven by a single JSON configuration file. This file allows you to enable or disable platforms, provide API credentials, and configure other settings without changing any code.

```json
{
  "platforms": {
    "wix": {
      "enabled": true,
      "site_id": "YOUR_WIX_SITE_ID",
      "api_key": "YOUR_WIX_API_KEY",
      "account_id": "YOUR_WIX_ACCOUNT_ID",
      "webhook_secret": "YOUR_WIX_WEBHOOK_SECRET"
    },
    "opencart": {
      "enabled": true,
      "store_url": "https://your-opencart-store.com/",
      "api_username": "YOUR_OPENCART_API_USERNAME",
      "api_key": "YOUR_OPENCART_API_KEY",
      "webhook_secret": "YOUR_OPENCART_WEBHOOK_SECRET"
    },
    "shopify": {
      "enabled": true,
      "shop_name": "your-shopify-store",
      "access_token": "YOUR_SHOPIFY_ADMIN_API_ACCESS_TOKEN",
      "api_version": "2026-01",
      "webhook_secret": "YOUR_SHOPIFY_WEBHOOK_SECRET"
    }
  }
}
```

## 5. API Reference

The Integration Gateway exposes the following API endpoints under the `/api/integrations/` prefix:

*   **`GET /health`**: Returns the health status of the gateway and all registered connectors.
*   **`GET /test-connections`**: Actively tests the connection to each enabled platform.
*   **`POST /appointments/sync`**: Triggers a synchronization of appointments from all or specified platforms.
*   **`POST /clients/sync`**: Triggers a synchronization of clients/customers.
*   **`POST /products/sync`**: Triggers a synchronization of products.
*   **`GET /b2b/companies`**: Retrieves a list of B2B companies from Shopify.
*   **`POST /b2b/companies`**: Creates a new B2B company on Shopify.

## 6. Webhook Reference

The Webhook Router listens for incoming webhooks and emits unified events. The following is a partial list of supported events:

| Platform | Original Event        | Unified Event         |
|----------|-----------------------|-----------------------|
| Wix      | `bookings/created`    | `appointment.created` |
| Wix      | `bookings/updated`    | `appointment.updated` |
| Shopify  | `orders/create`       | `order.created`       |
| Shopify  | `products/update`     | `product.updated`     |
| Shopify  | `customers/create`    | `customer.created`    |
| OpenCart | `order/created`       | `order.created`       |

## 7. Shopify B2B Integration

The Shopify B2B integration provides advanced features for wholesale and professional clients, leveraging Shopify's B2B on Shopify capabilities. This requires a **Shopify Plus** plan.

### Key B2B Features:

*   **Companies**: Manage B2B customer accounts as companies with multiple locations and contacts.
*   **Catalogs**: Assign specific product catalogs and price lists to different companies or locations.
*   **Draft Orders**: Create draft orders for B2B customers, which can be reviewed and approved before being converted into actual orders.
*   **GraphQL API**: The integration uses Shopify's GraphQL API for all B2B-related operations, providing more power and flexibility than the REST API.

## 8. Getting Started

1.  **Prerequisites**: Ensure you have Python 3.8+ and `pip` installed.
2.  **Clone Repository**: `git clone https://github.com/skintwin-ai/skintwin-integrations.git`
3.  **Install Dependencies**: `cd skintwin-integrations && pip install -r requirements.txt`
4.  **Configure**: Create a `config.json` file from the `config.example.json` template and fill in your API credentials.
5.  **Run Application**: `python main.py`
6.  **Test**: Access `http://localhost:5000/api/integrations/health` to verify that the gateway is running and all enabled connectors are healthy.
'''
