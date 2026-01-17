# SkinTwin Integration API Research Notes

## 1. Wix Appointment Bookings API

### Overview
- **Base URL**: `https://www.wixapis.com`
- **Authentication**: OAuth 2.0 with access tokens
- **Format**: REST API with JSON payloads

### Key APIs
1. **Services API** (`/bookings/v2/services`)
   - Create, manage, and query service offerings
   - Service types: Appointments, Classes, Courses

2. **Bookings Writer V2** (`/bookings/v2/bookings`)
   - Create single-service or multi-service bookings
   - Endpoint: `POST https://www.wixapis.com/_api/bookings-service/v2/bookings`

3. **Time Slots API** (`/bookings/v2/availability`)
   - Check availability of appointment slots
   - Query available time slots for scheduling

4. **Staff Members API**
   - Manage service providers and working hours

5. **Calendar API Integration**
   - Sync with external calendars (Google, Microsoft, Apple)

### Booking Flow
1. Query available services
2. Check time slot availability
3. Create booking with contact details
4. Process payment via Wix eCommerce
5. Receive confirmation and notifications

### Webhook Events
- Booking created/updated/cancelled
- Service changes
- Staff schedule updates

---

## 2. OpenCart API

### Overview
- **Base URL**: `https://{store}/index.php?route=api/{endpoint}`
- **Authentication**: API key + session token
- **Format**: REST API with JSON responses

### Authentication Flow
```python
# 1. Login to get api_token
POST /index.php?route=api/login
data={'username': 'Default', 'key': 'API_KEY_256_CHARS'}

# 2. Use api_token in subsequent requests
GET /index.php?route=api/cart/products&api_token={token}
```

### Key Endpoints
1. **Cart Operations**
   - `api/cart/add` - Add product to cart
   - `api/cart/edit` - Edit cart quantity
   - `api/cart/remove` - Remove from cart
   - `api/cart/products` - Get cart contents

2. **Customer Management**
   - `api/customer` - Set customer for session
   - Fields: firstname, lastname, email, telephone

3. **Order Management**
   - `api/order/add` - Create new order
   - `api/order/edit` - Update order
   - `api/order/history` - Add order history

4. **Shipping**
   - `api/shipping/address` - Set shipping address
   - `api/shipping/methods` - Get available methods
   - `api/shipping/method` - Set shipping method

5. **Payment**
   - `api/payment/address` - Set payment address
   - `api/payment/methods` - Get payment methods
   - `api/payment/method` - Set payment method

6. **Vouchers & Coupons**
   - `api/voucher` - Apply voucher
   - `api/coupon` - Apply coupon

### Notes
- API users have customer_id = 0
- IP whitelist required for API access
- Session-based authentication

---

## 3. Shopify B2B API

### Overview
- **Base URL**: `https://{shop}.myshopify.com/admin/api/{version}`
- **Authentication**: OAuth 2.0 or Admin API access token
- **Format**: REST and GraphQL APIs
- **B2B**: Requires Shopify Plus plan

### REST Admin API Pattern
```
https://{store_name}.myshopify.com/admin/api/2026-01/{resource}.json
```

### Key B2B Objects (GraphQL)
1. **Company**
   - Business entity making B2B purchases
   - Contains locations and contacts

2. **CompanyLocation**
   - Single location/branch of company
   - Billing/shipping addresses
   - Assigned catalogs, tax exemptions, payment terms

3. **CompanyContact**
   - Person acting on behalf of company
   - Associated with retail customer record

4. **Catalog**
   - Product selections and pricing for B2B
   - Assigned to company locations

### REST Endpoints
1. **Products**
   - `GET/POST /admin/api/2026-01/products.json`
   - `GET/PUT/DELETE /admin/api/2026-01/products/{id}.json`

2. **Orders**
   - `GET/POST /admin/api/2026-01/orders.json`
   - `GET/PUT /admin/api/2026-01/orders/{id}.json`

3. **Customers**
   - `GET/POST /admin/api/2026-01/customers.json`
   - `GET/PUT/DELETE /admin/api/2026-01/customers/{id}.json`

4. **Draft Orders (B2B)**
   - Create draft orders for company contacts
   - Send for approval and invoicing

### B2B Features
- Company management
- Catalog assignment per location
- Custom pricing levels
- Payment terms
- Tax exemptions
- Draft order workflow

### Rate Limits
- 40 requests per app per store per minute
- Replenishes at 2 requests/second
- 10x increase for Shopify Plus stores

### Webhooks
- Order creation/update/cancellation
- Product changes
- Customer updates
- Fulfillment events

---

## Integration Architecture Considerations

### Unified Data Model
- Map salon appointments to all three platforms
- Sync client/customer data bidirectionally
- Inventory synchronization for products

### Event-Driven Architecture
- Webhook handlers for real-time updates
- Message queue for async processing
- Event sourcing for audit trail

### Authentication Strategy
- Secure credential storage
- Token refresh mechanisms
- Multi-tenant support

### Error Handling
- Retry logic with exponential backoff
- Circuit breaker pattern
- Comprehensive logging
