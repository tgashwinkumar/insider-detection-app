# EtherScan v2 & The Graph API Knowledge Base

**Last Updated:** April 2026  
**Status:** Complete Reference for SENTINEL Backend Integration  
**Created For:** Insider Trading Detection System on Polygon

---

## Table of Contents

1. [Quick Reference](#quick-reference)
2. [EtherScan v2 API](#etherscan-v2-api)
3. [The Graph Network](#the-graph-network)
4. [Polygon Chain Configuration](#polygon-chain-configuration)
5. [Response Formats & Error Handling](#response-formats--error-handling)
6. [Validation Checklist](#validation-checklist)
7. [Rate Limits & Best Practices](#rate-limits--best-practices)
8. [Environment Variables](#environment-variables)

---

## Quick Reference

| Service | Purpose | Base URL | Auth | Polygon Support |
|---------|---------|----------|------|-----------------|
| **EtherScan v2** | Token transfers, wallet history, contract ABIs | `https://api.etherscan.io/v2/api` | API Key (Free) | ✅ `chainid=137` |
| **The Graph** | Historical trade indexing (OrderFilled events) | `https://gateway.thegraph.com/api/{KEY}/subgraphs/id/{ID}` | Optional (Free) | ✅ Polymarket subgraph |
| **Polymarket Gamma API** | Market metadata, search | `https://gamma-api.polymarket.com` | None | ✅ Native |
| **Polygon RPC (HTTP)** | Block data, transaction verification | `https://polygon-rpc.com` | None | ✅ Native |
| **Polygon RPC (WebSocket)** | Live event subscription | `wss://polygon-bor-rpc.publicnode.com` | None | ✅ Native |

---

## EtherScan v2 API

### Overview

EtherScan v2 is a **unified multi-chain API** supporting 60+ EVM-compatible blockchains, including Polygon. 
It replaces the deprecated PolygonScan API with identical functionality and syntax.

**Key Difference from v1:** All requests include `?chainid=` parameter to specify the target chain.

### Authentication

```
Endpoint: https://api.etherscan.io/v2/api
Required Parameter: ?apikey={YOUR_API_KEY}
Rate Limit: 5 requests/second (free tier)
Sign Up: https://etherscan.io/apis
```

### Chain IDs Reference

| Chain | Chain ID | Usage | For free ? |
|-------|----------|-------|-----|
| Ethereum | `1` | N/A for SENTINEL | - |
| Polygon PoS | `137` | **PRIMARY for SENTINEL** | - |
| Arbitrum One | `42161` | Reference | - |
| Base | `8453` | Reference | Not Available for free |
| BNB Smart Chain | `56` | Reference | - |

### API Modules & Endpoints

#### 1. **ACCOUNT MODULE** (`module=account`)

Used to retrieve wallet information, token transfers, and transaction history.

##### 1.1 `action=tokentx` — Token Transfers

**Purpose:** Get all token transfer events for a wallet or contract.

**Endpoint:**
```
GET https://api.etherscan.io/v2/api
  ?apikey={KEY}
  &chainid=137
  &module=account
  &action=tokentx
  &contractaddress={CONTRACT_ADDR}
  &address={WALLET_ADDR}
  &page=1
  &offset=10000
  &sort=asc
```

**Key Parameters:**
| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `apikey` | Yes | string | Your EtherScan API key |
| `chainid` | Yes | string | `137` for Polygon |
| `module` | Yes | string | `account` |
| `action` | Yes | string | `tokentx` |
| `contractaddress` | Yes | string | Token contract address (e.g., USDC.e: `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174`) |
| `address` | Yes | string | Wallet address to query |
| `page` | No | number | Pagination page (default: 1) |
| `offset` | No | number | Records per page (default: 10000, max: 10000) |
| `sort` | No | string | `asc` (earliest first) or `desc` (latest first) |
| `startblock` | No | number | Block number to start from |
| `endblock` | No | number | Block number to end at |

**Response Format:**
```json
{
  "status": "1",
  "message": "OK",
  "result": [
    {
      "blockNumber": "48000000",
      "timeStamp": "1741413668",
      "hash": "0xf0d056b8...",
      "nonce": "5",
      "blockHash": "0x7d1e...",
      "from": "0x...",
      "contractAddress": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
      "to": "0x...",
      "value": "100000000",
      "tokenName": "USD Coin",
      "tokenSymbol": "USDC",
      "tokenDecimal": "6",
      "transactionIndex": "0",
      "gas": "65000",
      "gasPrice": "30000000000",
      "gasUsed": "50000",
      "cumulativeGasUsed": "50000",
      "input": "0xa9059cbb...",
      "confirmations": "1000"
    }
  ]
}
```

**Use Case in SENTINEL:** Find the **first USDC.e deposit** timestamp for wallet age calculation (Factor 4).

**Implementation Note:**
```python
# Get earliest USDC.e transfer (first deposit)
response = requests.get(
    "https://api.etherscan.io/v2/api",
    params={
        "apikey": API_KEY,
        "chainid": "137",
        "module": "account",
        "action": "tokentx",
        "contractaddress": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        "address": wallet_address,
        "sort": "asc"
    }
)
if response.status_code == 200 and response.json()["status"] == "1":
    first_deposit = response.json()["result"][0]
    deposit_timestamp = int(first_deposit["timeStamp"])
```

---

##### 1.2 `action=txlist` — Transaction List

**Purpose:** Get all transactions for a wallet.

**Endpoint:**
```
GET https://api.etherscan.io/v2/api
  ?apikey={KEY}
  &chainid=137
  &module=account
  &action=txlist
  &address={WALLET_ADDR}
  &startblock=0
  &endblock=99999999
  &sort=asc
```

**Key Parameters:**
| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `address` | Yes | string | Wallet address |
| `startblock` | No | number | Start block (default: 0) |
| `endblock` | No | number | End block (default: latest) |
| `sort` | No | string | `asc` or `desc` |

**Response Format:** Array of transaction objects with `hash`, `from`, `to`, `value`, `input`, etc.

---

##### 1.3 `action=balance` — Native Token Balance

**Purpose:** Get current native token (MATIC) balance for wallet.

**Endpoint:**
```
GET https://api.etherscan.io/v2/api
  ?apikey={KEY}
  &chainid=137
  &module=account
  &action=balance
  &address={WALLET_ADDR}
  &tag=latest
```

**Response Format:**
```json
{
  "status": "1",
  "message": "OK",
  "result": "2500000000000000000"
}
```

---

##### 1.4 `action=tokenbalance` — Token Balance at Address

**Purpose:** Get current balance of a specific token at a wallet.

**Endpoint:**
```
GET https://api.etherscan.io/v2/api
  ?apikey={KEY}
  &chainid=137
  &module=account
  &action=tokenbalance
  &contractaddress={TOKEN_ADDR}
  &address={WALLET_ADDR}
  &tag=latest
```

---

#### 2. **CONTRACT MODULE** (`module=contract`)

##### 2.1 `action=getabi` — Get Contract ABI

**Purpose:** Retrieve the JSON ABI of a verified smart contract.

**Endpoint:**
```
GET https://api.etherscan.io/v2/api
  ?apikey={KEY}
  &chainid=137
  &module=contract
  &action=getabi
  &address={CONTRACT_ADDR}
```

**Response Format:**
```json
{
  "status": "1",
  "message": "OK",
  "result": "[{\"constant\":false,\"inputs\":[...],\"name\":\"transfer\",\"outputs\":[...],\"type\":\"function\"}, ...]"
}
```

---

##### 2.2 `action=getsourcecode` — Get Contract Source Code

**Purpose:** Retrieve the source code and compilation details of a verified contract.

**Endpoint:**
```
GET https://api.etherscan.io/v2/api
  ?apikey={KEY}
  &chainid=137
  &module=contract
  &action=getsourcecode
  &address={CONTRACT_ADDR}
```

**Response Format:**
```json
{
  "status": "1",
  "message": "OK",
  "result": [
    {
      "SourceCode": "pragma solidity ^0.8.0; ...",
      "ContractName": "ERC20",
      "CompilerVersion": "v0.8.0",
      "OptimizationUsed": "1",
      "Runs": "200"
    }
  ]
}
```

---

#### 3. **LOGS MODULE** (`module=logs`)

##### 3.1 `action=getLogs` — Get Event Logs

**Purpose:** Retrieve event logs (events) from contracts using topic filtering.

**Endpoint:**
```
GET https://api.etherscan.io/v2/api
  ?apikey={KEY}
  &chainid=137
  &module=logs
  &action=getLogs
  &fromBlock=40000000
  &toBlock=50000000
  &address={CONTRACT_ADDR}
  &topic0={EVENT_SIGNATURE}
  &page=1
  &offset=1000
```

**Key Parameters:**
| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `fromBlock` | Yes | number | Start block |
| `toBlock` | Yes | number | End block (max 5000 block range) |
| `address` | No | string | Contract address to filter by |
| `topic0` | No | string | Event signature hash (e.g., `0xddf252ad...` for Transfer) |
| `topic1` | No | string | Indexed parameter 1 |
| `topic2` | No | string | Indexed parameter 2 |
| `topic3` | No | string | Indexed parameter 3 |

---

#### 4. **TRANSACTION MODULE** (`module=transaction`)

##### 4.1 `action=gettxreceiptstatus` — Transaction Receipt Status

**Purpose:** Check if a transaction was successful.

**Endpoint:**
```
GET https://api.etherscan.io/v2/api
  ?apikey={KEY}
  &chainid=137
  &module=transaction
  &action=gettxreceiptstatus
  &txhash={TX_HASH}
```

**Response Format:**
```json
{
  "status": "1",
  "message": "OK",
  "result": {
    "isError": "0",
    "errDescription": ""
  }
}
```

---

#### 5. **BLOCK MODULE** (`module=block`)

##### 5.1 `action=getblocknobytime` — Get Block by Timestamp

**Purpose:** Retrieve block number for a given timestamp.

**Endpoint:**
```
GET https://api.etherscan.io/v2/api
  ?apikey={KEY}
  &chainid=137
  &module=block
  &action=getblocknobytime
  &timestamp=1741413668
  &closest=before
```

**Parameters:**
- `timestamp` — Unix timestamp
- `closest` — `before` or `after` (how to find nearest block)

---

#### 6. **STATS MODULE** (`module=stats`)

##### 6.1 `action=tokensupply` — Token Total Supply

**Purpose:** Get total supply of a token.

**Endpoint:**
```
GET https://api.etherscan.io/v2/api
  ?apikey={KEY}
  &chainid=137
  &module=stats
  &action=tokensupply
  &contractaddress={TOKEN_ADDR}
```

---

#### 7. **GASTRACKER MODULE** (`module=gastracker`)

##### 7.1 `action=gasoracle` — Gas Price Oracle

**Purpose:** Get current gas prices (safe, standard, fast).

**Endpoint:**
```
GET https://api.etherscan.io/v2/api
  ?apikey={KEY}
  &chainid=137
  &module=gastracker
  &action=gasoracle
```

**Response Format:**
```json
{
  "status": "1",
  "message": "OK",
  "result": {
    "SafeGasPrice": "30",
    "StandardGasPrice": "35",
    "FastGasPrice": "40"
  }
}
```

---

### EtherScan v2 USDC.e Configuration for Polygon

**Token Contract Address (Polygon):**
```
0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174
```

**Token Details:**
- Name: USD Coin
- Symbol: USDC.e (e = "Ethereum" bridge)
- Decimals: 6
- Chain: Polygon PoS (Mainnet)

**For SENTINEL:** Use this contract address in `tokentx` queries to track USDC.e deposits.

---

## The Graph Network

### Overview

The Graph is a **decentralized indexing protocol** for querying blockchain data via GraphQL. It hosts pre-indexed subgraphs for Polymarket, eliminating the need to scan raw blockchain logs. Multiple specialized subgraphs index different aspects of Polymarket activity: historical trades (OrderFilled), user positions and PnL tracking, open interest, and market activity (splits, merges, redemptions).

**For FLARE:** Primary use is the Orderbook/Activity subgraphs for historical trade indexing and wallet enrichment.

### Authentication

**Decentralized Network (Recommended):**
- Endpoint: `https://gateway.thegraph.com/api/{API_KEY}/subgraphs/id/{SUBGRAPH_ID}`
- Requires free API key from https://thegraph.com/studio
- Rate limit: 100,000 queries/month (free tier)
- Supports paid Growth Plan for higher volumes

**Hosted Service (Legacy):**
- Endpoint: `https://api.thegraph.com/subgraphs/name/polymarket/polymarket`
- No API key required
- Deprecated but still functional
- Not recommended for new development

---

## Polymarket Subgraph Registry

The Graph Network hosts 7 official Polymarket subgraphs, each specializing in different data domains.

| # | Name | Subgraph ID | Purpose | Network | Signal |
|---|------|-------------|---------|---------|--------|
| 1 | **Polymarket (Main)** | `81Dm16JjuFSrqz813HysXoUPvzTwE7fsfPk2RTf66nyC` | Core markets, positions, FPMMs, liquidity | Polygon | 11.0K GRT |
| 2 | **Activity Polygon** | `Bx1W4S7kDVxs9gC3s2G6DS8kdNBJNVhMviCtin2DiBp` | Splits, merges, redemptions, NegRisk conversions | Polygon | 499.3 GRT |
| 3 | **Profit & Loss** | `6c58N5U4MtQE2Y8njfVrrAfRykzfqajMGeTMEvMmskVz` | User positions, realized PnL, trading history | Polygon | - |
| 4 | **Open Interest** | `ELaW6RtkbmYNmMMU6hEPsghG9Ko3EXSmiRkH855M4qfF` | Market open interest, global metrics | Polygon | - |
| 5 | **Orderbook** | `7fu2DWYK93ePfzB24c2wrP94S3x4LGHUrQxphhoEypyY` | Order fills, matched orders, volume, spread analytics | Polygon | - |
| 6 | **Names** | `22CoTbEtpv6fURB6moTNfJPWNUPXtiFGRA8h1zajMha3` | Human-readable market titles & questions | Arbitrum | - |
| 7 | **Order Filled Events** | `EZCTgSzLPuBSqQcuR3ifeiKHKBnpjHSNbYpty8Mnjm9D` | OrderFilled events (supplementary) | Polygon | - |

### Query Endpoints

Each subgraph is queryable via:

```
https://gateway.thegraph.com/api/{API_KEY}/subgraphs/id/{SUBGRAPH_ID}
```

Replace `{API_KEY}` with your free key from https://thegraph.com/studio and `{SUBGRAPH_ID}` with the ID from the table above.

---

## Complete GraphQL Schemas

### 1. Orderbook Subgraph Schema

```graphql
type OrderFilledEvent @entity {
  "Transaction hash + Order hash (unique ID)"
  id: ID!
  "Transaction hash"
  transactionHash: Bytes!
  "Unix timestamp when filled"
  timestamp: BigInt!
  "Order hash"
  orderHash: Bytes!
  "Maker address (order initiator)"
  maker: String!
  "Taker address (order acceptor)"
  taker: String!
  "Asset ID offered by maker"
  makerAssetId: String!
  "Asset ID offered by taker"
  takerAssetId: String!
  "Amount filled by maker (wei)"
  makerAmountFilled: BigInt!
  "Amount filled by taker (wei)"
  takerAmountFilled: BigInt!
  "Fee paid by maker (wei)"
  fee: BigInt!
}

type OrdersMatchedEvent @entity {
  "Transaction hash (unique ID)"
  id: ID!
  "Unix timestamp when matched"
  timestamp: BigInt!
  "Maker asset ID (as BigInt)"
  makerAssetID: BigInt!
  "Taker asset ID (as BigInt)"
  takerAssetID: BigInt!
  "Amount filled by maker"
  makerAmountFilled: BigInt!
  "Amount filled by taker"
  takerAmountFilled: BigInt!
}

type Orderbook @entity {
  "Token ID (asset/market identifier)"
  id: ID!
  "Total number of trades for this orderbook"
  tradesQuantity: BigInt!
  "Number of buy orders filled"
  buysQuantity: BigInt!
  "Number of sell orders filled"
  sellsQuantity: BigInt!
  "Total volume (USDC base units)"
  collateralVolume: BigInt!
  "Total volume (scaled by 10^6)"
  scaledCollateralVolume: BigDecimal!
  "Buy volume (USDC base units)"
  collateralBuyVolume: BigInt!
  "Buy volume (scaled)"
  scaledCollateralBuyVolume: BigDecimal!
  "Sell volume (USDC base units)"
  collateralSellVolume: BigInt!
  "Sell volume (scaled)"
  scaledCollateralSellVolume: BigDecimal!
}

type OrdersMatchedGlobal @entity {
  "ID is always empty string (singleton)"
  id: ID!
  "Global trade count"
  tradesQuantity: BigInt!
  "Global buy count"
  buysQuantity: BigInt!
  "Global sell count"
  sellsQuantity: BigInt!
  "Global volume (scaled)"
  collateralVolume: BigDecimal!
  "Global buy volume (scaled)"
  scaledCollateralBuyVolume: BigDecimal!
  "Global sell volume (scaled)"
  scaledCollateralSellVolume: BigDecimal!
}

type MarketData @entity {
  "ERC1155 token ID"
  id: ID!
  "Condition ID"
  condition: String!
  "Outcome index (0-based)"
  outcomeIndex: BigInt
}
```

---

### 2. Activity Subgraph Schema

```graphql
type Split @entity {
  "Transaction hash (unique)"
  id: ID!
  "Unix timestamp"
  timestamp: BigInt!
  "Address performing split"
  stakeholder: String!
  "Condition being split"
  condition: String!
  "Amount being split (wei)"
  amount: BigInt!
}

type Merge @entity {
  "Transaction hash (unique)"
  id: ID!
  "Unix timestamp"
  timestamp: BigInt!
  "Address performing merge"
  stakeholder: String!
  "Condition being merged"
  condition: String!
  "Amount being merged (wei)"
  amount: BigInt!
}

type Redemption @entity {
  "Transaction hash (unique)"
  id: ID!
  "Unix timestamp"
  timestamp: BigInt!
  "Address redeeming"
  redeemer: String!
  "Condition being redeemed"
  condition: String!
  "Index sets being redeemed"
  indexSets: [BigInt!]!
  "Collateral claimed (wei)"
  payout: BigInt!
}

type NegRiskConversion @entity {
  "Transaction hash (unique)"
  id: ID!
  "Unix timestamp"
  timestamp: BigInt!
  "Address performing conversion"
  stakeholder: String!
  "Neg Risk market ID"
  negRiskMarketId: String!
  "Amount being converted (wei)"
  amount: BigInt!
  "Index set of outcome tokens"
  indexSet: BigInt!
  "Number of questions at time of conversion"
  questionCount: Int!
}

type NegRiskEvent @entity {
  "Neg Risk market ID"
  id: ID!
  "Question count for this market"
  questionCount: Int!
}

type FixedProductMarketMaker @entity {
  "FPMM contract address"
  id: ID!
}

type Position @entity {
  "ERC1155 token ID"
  id: ID!
  "Condition ID"
  condition: String!
  "Outcome index"
  outcomeIndex: BigInt!
}

type Condition @entity {
  "Condition ID"
  id: ID!
}
```

---

### 3. PnL Subgraph Schema

```graphql
type userPosition @entity {
  "User + Token ID"
  id: ID!
  "User wallet address"
  user: String!
  "Token ID of the position"
  tokenId: String!
  "Current amount held"
  amount: BigInt!
  "Average entry price"
  avgPrice: BigDecimal!
  "Realized profit/loss"
  realizedPnl: BigDecimal!
  "Total value bought"
  totalBought: BigDecimal!
}

type condition @entity {
  "Condition ID"
  id: ID!
  "Position IDs within this condition"
  positionIds: [String!]
  "Payout numerators for each outcome"
  payoutNumerators: [BigInt!]
  "Payout denominator"
  payoutDenominator: BigInt
}

type fpmm @entity {
  "Market maker address"
  id: ID!
  "Condition ID"
  conditionId: String!
}

type negRiskEvent @entity {
  "Neg Risk market ID"
  id: ID!
  "Question count"
  questionCount: Int!
}
```

---

### 4. Open Interest Subgraph Schema

```graphql
type globalOpenInterest @entity {
  "ID is always empty string (singleton)"
  id: ID!
  "Global open interest (wei)"
  amount: BigInt!
}

type marketOpenInterest @entity {
  "Condition ID"
  id: ID!
  "Open interest for this market (wei)"
  amount: BigInt!
}

type condition @entity {
  "Condition ID"
  id: ID!
}

type negRiskEvent @entity {
  "Neg Risk market ID"
  id: ID!
  "Fee in basis points (bps)"
  feeBps: Int!
  "Question count"
  questionCount: Int!
}
```

---

### 5. Names Subgraph Schema

```graphql
type Market @entity {
  "Market ID (questionID)"
  id: ID!
  "Question ID"
  questionID: String!
  "Human-readable market title/question"
  question: String!
  "Market creator address"
  creator: Bytes!
  "Creation timestamp"
  timestamp: BigInt!
  "UMA oracle reward"
  reward: BigInt!
}

type QuestionInitialized @entity {
  id: ID!
  "Event fired when market is created"
}

type QuestionResolved @entity {
  id: ID!
  "Payout values"
  payouts: [BigInt!]
  "Resolution timestamp"
  resolvedTimestamp: BigInt!
}

type PriceRequest @entity {
  id: ID!
  "Oracle price request data"
}
```

---

## GraphQL Query Examples

### Orderbook Subgraph

**Fetch OrderFilled Events (Main FLARE Use Case):**
```graphql
{
  orderFilledEvents(
    first: 1000,
    where: { takerAssetId: "0xda8b2e1e..." },
    orderBy: timestamp,
    orderDirection: asc
  ) {
    id
    transactionHash
    timestamp
    maker
    taker
    takerAssetId
    takerAmountFilled
    fee
  }
}
```

**Top Traders by Volume:**
```graphql
{
  orderFilledEvents(
    first: 100,
    orderBy: takerAmountFilled,
    orderDirection: desc
  ) {
    maker
    taker
    takerAmountFilled
    timestamp
  }
}
```

**Recent Matched Orders:**
```graphql
{
  ordersMatchedEvents(
    first: 50,
    orderBy: timestamp,
    orderDirection: desc
  ) {
    id
    timestamp
    makerAssetID
    takerAssetID
    makerAmountFilled
    takerAmountFilled
  }
}
```

**Global Trade Statistics:**
```graphql
{
  ordersMatchedGlobals {
    id
    tradesQuantity
    buysQuantity
    sellsQuantity
    scaledCollateralVolume
    scaledCollateralBuyVolume
    scaledCollateralSellVolume
  }
}
```

**Market Volume for Specific Asset:**
```graphql
{
  orderbooks(
    where: { id: "TOKEN_ID" }
  ) {
    id
    tradesQuantity
    collateralVolume
    scaledCollateralVolume
    buysQuantity
    sellsQuantity
    scaledCollateralBuyVolume
    scaledCollateralSellVolume
  }
}
```

---

### Activity Subgraph

**Recent Redemptions (Largest Payouts):**
```graphql
{
  redemptions(
    orderBy: payout,
    orderDirection: desc,
    first: 20
  ) {
    id
    timestamp
    redeemer
    condition
    indexSets
    payout
  }
}
```

**User Activity (All Types):**
```graphql
{
  splits(where: { stakeholder: "0xUSER..." }) {
    id
    timestamp
    condition
    amount
  }
  merges(where: { stakeholder: "0xUSER..." }) {
    id
    timestamp
    condition
    amount
  }
  redemptions(where: { redeemer: "0xUSER..." }) {
    id
    timestamp
    condition
    payout
  }
  negRiskConversions(where: { stakeholder: "0xUSER..." }) {
    id
    timestamp
    negRiskMarketId
    amount
  }
}
```

**Splits and Merges by Condition:**
```graphql
{
  splits(
    where: { condition: "CONDITION_ID" },
    orderBy: timestamp,
    orderDirection: desc
  ) {
    id
    stakeholder
    amount
    timestamp
  }
  merges(
    where: { condition: "CONDITION_ID" },
    orderBy: timestamp,
    orderDirection: desc
  ) {
    id
    stakeholder
    amount
    timestamp
  }
}
```

**Large Operations (amount > 1 USDC):**
```graphql
{
  splits(
    where: { amount_gt: "1000000" },
    orderBy: amount,
    orderDirection: desc,
    first: 50
  ) {
    id
    stakeholder
    condition
    amount
    timestamp
  }
  merges(
    where: { amount_gt: "1000000" },
    orderBy: amount,
    orderDirection: desc,
    first: 50
  ) {
    id
    stakeholder
    condition
    amount
    timestamp
  }
}
```

**Neg Risk Conversions:**
```graphql
{
  negRiskConversions(
    orderBy: timestamp,
    orderDirection: desc,
    first: 100
  ) {
    id
    stakeholder
    negRiskMarketId
    amount
    questionCount
    timestamp
  }
}
```

---

### PnL Subgraph

**Top Profitable Users:**
```graphql
{
  userPositions(
    where: { realizedPnl_gt: "0" },
    orderBy: realizedPnl,
    orderDirection: desc,
    first: 50
  ) {
    user
    tokenId
    amount
    avgPrice
    realizedPnl
    totalBought
  }
}
```

**User PnL Summary:**
```graphql
{
  userPositions(
    where: { user: "0xWALLET..." },
    orderBy: realizedPnl,
    orderDirection: desc
  ) {
    id
    tokenId
    amount
    avgPrice
    realizedPnl
    totalBought
  }
}
```

**Largest Positions:**
```graphql
{
  userPositions(
    where: { amount_gt: "1000000000000000000" },
    orderBy: amount,
    orderDirection: desc,
    first: 100
  ) {
    user
    tokenId
    amount
    avgPrice
    realizedPnl
  }
}
```

---

### Open Interest Subgraph

**Global Open Interest:**
```graphql
{
  globalOpenInterests {
    amount
  }
}
```

**Top Markets by OI:**
```graphql
{
  marketOpenInterests(
    orderBy: amount,
    orderDirection: desc,
    first: 50
  ) {
    id
    amount
  }
}
```

**Markets with Significant OI:**
```graphql
{
  marketOpenInterests(
    where: { amount_gt: "1000000000000000000" },
    orderBy: amount,
    orderDirection: desc
  ) {
    id
    amount
  }
}
```

**Neg Risk Markets:**
```graphql
{
  negRiskEvents(
    orderBy: questionCount,
    orderDirection: desc
  ) {
    id
    feeBps
    questionCount
  }
}
```

---

## GraphQL API Reference

### Complete Filter Operators

| Operator | Example | Matches |
|---|---|---|
| `field` | `where: { status: "active" }` | Exact match |
| `field_not` | `where: { status_not: "inactive" }` | Not equal |
| `field_gt` | `where: { amount_gt: "1000" }` | Greater than |
| `field_lt` | `where: { amount_lt: "1000" }` | Less than |
| `field_gte` | `where: { amount_gte: "1000" }` | Greater than or equal |
| `field_lte` | `where: { amount_lte: "1000" }` | Less than or equal |
| `field_in` | `where: { status_in: ["active", "pending"] }` | Value in array |
| `field_not_in` | `where: { status_not_in: ["deleted"] }` | Value not in array |
| `field_contains` | `where: { name_contains: "poly" }` | Substring (case-sensitive) |
| `field_contains_nocase` | `where: { name_contains_nocase: "POLY" }` | Substring (case-insensitive) |
| `field_starts_with` | `where: { name_starts_with: "poly" }` | Prefix match |
| `field_starts_with_nocase` | `where: { name_starts_with_nocase: "POLY" }` | Prefix (case-insensitive) |
| `field_ends_with` | `where: { name_ends_with: "market" }` | Suffix match |
| `field_ends_with_nocase` | `where: { name_ends_with_nocase: "MARKET" }` | Suffix (case-insensitive) |
| `field_` | `where: { owner_: { name: "Alice" } }` | Filter via related entity |

### Pagination

**Limit + Offset (simple, slower for large datasets):**
```graphql
{
  orderFilledEvents(first: 1000, skip: 1000) {
    id
  }
}
```

**Cursor-based (recommended for deep pagination):**
```graphql
query manyEvents($lastID: String) {
  orderFilledEvents(first: 1000, where: { id_gt: $lastID }) {
    id
    timestamp
  }
}
```

Parameters:
- `first`: max 1000, default 100
- `skip`: offset (expensive for large skip values)
- `id_gt`: cursor-based offset (more efficient)

### Logical Operators

**AND (explicit):**
```graphql
{
  orderFilledEvents(
    where: {
      and: [
        { timestamp_gte: "1700000000" },
        { takerAmountFilled_gt: "1000000" }
      ]
    }
  ) {
    id
  }
}
```

**AND (shorthand — comma-separated):**
```graphql
{
  orderFilledEvents(
    where: {
      timestamp_gte: "1700000000",
      takerAmountFilled_gt: "1000000"
    }
  ) {
    id
  }
}
```

**OR:**
```graphql
{
  orderFilledEvents(
    where: {
      or: [
        { maker: "0xALICE..." },
        { maker: "0xBOB..." }
      ]
    }
  ) {
    id
  }
}
```

### Time-Travel Queries (Historical State)

**By block number:**
```graphql
{
  orderFilledEvents(block: { number: 50000000 }) {
    id
    timestamp
  }
}
```

**By block hash:**
```graphql
{
  orderFilledEvents(block: { hash: "0xabc..." }) {
    id
    timestamp
  }
}
```

### Metadata Query (Health Check)

```graphql
{
  _meta(block: { number: 999999999 }) {
    block {
      number
      hash
      timestamp
    }
    deployment
    hasIndexingErrors
  }
}
```

Useful for verifying subgraph sync status before making data queries.

---

## Best Practices

### 1. Use Cursor-Based Pagination for Large Datasets

**❌ Avoid:**
```graphql
{
  orderFilledEvents(first: 1000, skip: 50000) { ... }  # Expensive
}
```

**✅ Use:**
```graphql
query fetchMore($lastID: String) {
  orderFilledEvents(first: 1000, where: { id_gt: $lastID }) {
    id
    timestamp
  }
}
```

### 2. Always Check `_meta` Health Before Processing

```graphql
{
  _meta {
    hasIndexingErrors
    block { number }
  }
}
```

If `hasIndexingErrors` is `true`, data may be stale or incomplete.

### 3. Batch Multiple Filters When Possible

Instead of multiple queries, use `_in` operator:

```graphql
{
  orderFilledEvents(
    where: { takerAssetId_in: ["0x123", "0x456", "0x789"] }
  ) {
    id
  }
}
```

### 4. Set Reasonable `first` Limits

- Default 100 is safe
- Max 1000 per query
- Paginate if you need more

### 5. Cache Results Locally

Polymarket data rarely changes retroactively. Cache OrderFilled events with TTL to reduce API quota usage.

---

## Graph Explorer Interactive Playgrounds

Test queries visually before deploying code:

- [Main Polymarket](https://thegraph.com/explorer/subgraphs/81Dm16JjuFSrqz813HysXoUPvzTwE7fsfPk2RTf66nyC?view=Query&chain=arbitrum-one)
- [Activity Subgraph](https://thegraph.com/explorer/subgraphs/Bx1W4S7kDVxs9gC3s2G6DS8kdNBJNVhMviCtin2DiBp?view=Query&chain=arbitrum-one)
- [PnL Subgraph](https://thegraph.com/explorer/subgraphs/6c58N5U4MtQE2Y8njfVrrAfRykzfqajMGeTMEvMmskVz?view=Query&chain=arbitrum-one)
- [Open Interest](https://thegraph.com/explorer/subgraphs/ELaW6RtkbmYNmMMU6hEPsghG9Ko3EXSmiRkH855M4qfF?view=Query&chain=arbitrum-one)
- [Orderbook](https://thegraph.com/explorer/subgraphs/7fu2DWYK93ePfzB24c2wrP94S3x4LGHUrQxphhoEypyY)

---

## GitHub Repository Structure

Official Polymarket subgraph repository: https://github.com/Polymarket/polymarket-subgraph

```
polymarket-subgraph/
├── activity-subgraph/           # Splits, merges, redemptions, NegRisk
├── fpmm-subgraph/               # Main Polymarket core data
├── oi-subgraph/                 # Open interest tracking
├── orderbook-subgraph/          # Order fills, volume, analytics
├── pnl-subgraph/                # Profit/loss per user/position
├── sports-oracle-subgraph/      # Sports oracle data
├── fee-module/                  # Fee tracking
├── wallet/                      # Wallet-specific data
├── docker-compose.yml           # Local deployment
├── subgraph.yaml                # Manifest
└── yarn.lock
```

Key contracts indexed:
- `gnosis/conditional-tokens-contracts`
- `gnosis/conditional-tokens-market-makers`
- `Polymarket/ctf-exchange`
- `Polymarket/neg-risk-ctf-adapter`

Build & deploy:
```bash
yarn {subgraph}:codegen      # Generate types
yarn {subgraph}:build        # Build subgraph
yarn {subgraph}:deploy-local # Deploy locally
goldsky subgraph deploy      # Deploy to Goldsky
```

---

## Polygon Chain Configuration

### Network Details

| Property | Value |
|----------|-------|
| **Network Name** | Polygon (PoS) |
| **Chain ID** | 137 |
| **Currency** | MATIC |
| **RPC URL (HTTP)** | `https://polygon-rpc.com` |
| **RPC URL (WebSocket)** | `wss://polygon-bor-rpc.publicnode.com` |
| **Block Explorer** | `https://polygonscan.com` |
| **Block Time** | ~2 seconds |

### Key Contracts on Polygon

| Contract | Address | Purpose |
|----------|---------|---------|
| **USDC.e** | `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174` | Stablecoin for trading |
| **CTF Exchange** | `0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E` | Polymarket trading contract |
| **Conditional Token Framework** | `0xCeAfC9B8FF2F43F2f46fdA96Eab7fFdD16DF6BA3` | CTF implementation |

### Public RPC Endpoints

```
HTTP:  https://polygon-rpc.com
HTTP2: https://rpc.ankr.com/polygon
WebSocket: wss://polygon-bor-rpc.publicnode.com
WebSocket2: wss://polygon.publicnode.com
```

---

## Response Formats & Error Handling

### Standard Response Envelope (EtherScan v2)

All successful EtherScan v2 responses follow this format:

```json
{
  "status": "1",
  "message": "OK",
  "result": [/* data */]
}
```

### Error Response (EtherScan v2)

```json
{
  "status": "0",
  "message": "NOTOK",
  "result": "Max rate limit reached"
}
```

### Common EtherScan Error Messages

| Status | Message | Meaning |
|--------|---------|---------|
| `0` | `NOTOK` | General error or no data found |
| `0` | `Max rate limit reached` | Exceeded 5 req/s rate limit |
| `0` | `Invalid API Key` | API key is incorrect or inactive |
| `0` | `Invalid address format` | Wallet address is malformed |
| `1` | `OK` | Success (standard response) |
| `1` | `No transactions found` | Wallet has no history (normal for new wallets) |

### GraphQL Response Format (The Graph)

Success:
```json
{
  "data": {
    "orderFilledEvents": [
      { /* event data */ }
    ]
  }
}
```

Error:
```json
{
  "errors": [
    {
      "message": "Field \"invalidField\" doesn't exist on type \"OrderFilledEvent\"",
      "locations": [{ "line": 3, "column": 5 }]
    }
  ]
}
```

### Common GraphQL Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Field "..." doesn't exist` | Wrong field name in query | Check schema documentation |
| `Argument "..." expected type` | Wrong parameter type | Verify query syntax |
| `Cannot query field "..." on type` | Field not available on entity | Use correct entity type |
| `Timeout: 30000ms exceeded` | Query too large (fetching 10000+ records) | Reduce `first` parameter, paginate |

---

## Validation Checklist

### Test 1: EtherScan v2 API — Wallet Balance

**Purpose:** Verify API key and Polygon connectivity

**Request:**
```bash
curl "https://api.etherscan.io/v2/api?apikey=YOUR_KEY&chainid=137&module=account&action=balance&address=0x0000000000000000000000000000000000000000&tag=latest"
```

**Expected Response:**
```json
{
  "status": "1",
  "message": "OK",
  "result": "..."
}
```

**Success Criteria:** `status == "1"` and `message == "OK"`

---

### Test 2: EtherScan v2 API — USDC.e Transfers

**Purpose:** Verify token transfer query works

**Request:**
```bash
curl "https://api.etherscan.io/v2/api?apikey=YOUR_KEY&chainid=137&module=account&action=tokentx&contractaddress=0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174&address=0x1234567890123456789012345678901234567890&sort=asc"
```

**Expected Response:**
```json
{
  "status": "1",
  "message": "OK",
  "result": [
    {
      "blockNumber": "48000000",
      "timeStamp": "1741413668",
      "hash": "0x...",
      "from": "0x...",
      "to": "0x...",
      "value": "100000000",
      "tokenName": "USD Coin",
      "tokenDecimal": "6"
    }
  ]
}
```

**Success Criteria:**
- `status == "1"`
- Array is empty OR contains token transfer objects
- Each transfer has `timeStamp`, `value`, `tokenDecimal`

---

### Test 3: The Graph — Polymarket Subgraph Availability

**Purpose:** Verify The Graph subgraph is accessible and queryable

**Request:**
```bash
curl -X POST "https://api.thegraph.com/subgraphs/name/polymarket/polymarket" \
  -H "Content-Type: application/json" \
  -d '{"query":"{ orderFilledEvents(first: 1) { id } }"}'
```

**Expected Response:**
```json
{
  "data": {
    "orderFilledEvents": [
      { "id": "0x..." }
    ]
  }
}
```

**Success Criteria:**
- Status code: `200`
- No `errors` field in response
- `data.orderFilledEvents` is an array (possibly empty, possibly with results)

---

### Test 4: The Graph Schema Introspection

**Purpose:** Verify schema and available fields

**Request:**
```bash
curl -X POST "https://api.thegraph.com/subgraphs/name/polymarket/polymarket" \
  -H "Content-Type: application/json" \
  -d '{"query":"{ __schema { queryType { name } types { name } } }"}'
```

**Expected Response:**
```json
{
  "data": {
    "__schema": {
      "queryType": {
        "name": "Query"
      },
      "types": [
        { "name": "OrderFilledEvent" },
        { "name": "FPMM" },
        { "name": "Position" }
      ]
    }
  }
}
```

**Success Criteria:**
- Schema returns successfully
- Contains `OrderFilledEvent`, `FPMM`, `Position` types

---

### Test 5: Live Polygon RPC WebSocket

**Purpose:** Verify WebSocket connectivity for live event listening

**Request (Python):**
```python
import asyncio
from web3 import Web3

async def test_rpc():
    w3 = Web3(Web3.WebsocketProvider("wss://polygon-bor-rpc.publicnode.com"))
    block = await w3.eth.get_block("latest")
    print(f"Latest block: {block.number}")
    assert block.number > 0

asyncio.run(test_rpc())
```

**Expected Output:**
```
Latest block: 48123456
```

**Success Criteria:** Returns a block number > 0

---

### Python Validation Script

Save as `validate_apis.py`:

```python
#!/usr/bin/env python3
"""
Validate EtherScan v2 and The Graph connectivity
Run before deploying SENTINEL backend
"""

import requests
import json
import time
from datetime import datetime

def test_etherscan(api_key):
    """Test EtherScan v2 API"""
    print("\n" + "="*60)
    print("TESTING ETHERSCAN V2 API")
    print("="*60)
    
    # Test 1: Balance query
    print("\n[1] Testing account balance query...")
    try:
        url = "https://api.etherscan.io/v2/api"
        params = {
            "apikey": api_key,
            "chainid": "137",
            "module": "account",
            "action": "balance",
            "address": "0x0000000000000000000000000000000000000000"
        }
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if data.get("status") == "1":
            print("✅ PASS: Balance query successful")
        else:
            print(f"❌ FAIL: {data.get('message')}")
            return False
    except Exception as e:
        print(f"❌ FAIL: {e}")
        return False
    
    # Test 2: Token transfer query
    print("\n[2] Testing USDC.e token transfer query...")
    try:
        params = {
            "apikey": api_key,
            "chainid": "137",
            "module": "account",
            "action": "tokentx",
            "contractaddress": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
            "address": "0x1111111111111111111111111111111111111111",
            "page": "1",
            "offset": "10",
            "sort": "asc"
        }
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if data.get("status") in ["0", "1"]:
            # Status 0 with "No transactions found" is OK
            print(f"✅ PASS: Token query returned {len(data.get('result', []))} transfers")
        else:
            print(f"❌ FAIL: {data.get('message')}")
            return False
    except Exception as e:
        print(f"❌ FAIL: {e}")
        return False
    
    print("\n✅ EtherScan v2 API: VALIDATED")
    return True

def test_the_graph():
    """Test The Graph Polymarket subgraph"""
    print("\n" + "="*60)
    print("TESTING THE GRAPH POLYMARKET SUBGRAPH")
    print("="*60)
    
    # Test 1: Basic query
    print("\n[1] Testing basic OrderFilledEvent query...")
    try:
        url = "https://api.thegraph.com/subgraphs/name/polymarket/polymarket"
        query = """{
            orderFilledEvents(first: 1) {
                id
                timestamp
            }
        }"""
        
        response = requests.post(
            url,
            json={"query": query},
            timeout=10,
            headers={"Content-Type": "application/json"}
        )
        data = response.json()
        
        if "errors" in data:
            print(f"❌ FAIL: {data['errors'][0]['message']}")
            return False
        elif "data" in data:
            events = data["data"].get("orderFilledEvents", [])
            print(f"✅ PASS: Query returned {len(events)} events")
        else:
            print(f"❌ FAIL: Unexpected response format")
            return False
    except Exception as e:
        print(f"❌ FAIL: {e}")
        return False
    
    # Test 2: Schema introspection
    print("\n[2] Testing schema introspection...")
    try:
        schema_query = """{
            __schema {
                queryType {
                    name
                }
                types {
                    name
                }
            }
        }"""
        
        response = requests.post(
            url,
            json={"query": schema_query},
            timeout=10,
            headers={"Content-Type": "application/json"}
        )
        data = response.json()
        
        if "errors" not in data and "data" in data:
            types = [t["name"] for t in data["data"]["__schema"]["types"]]
            has_required = all(t in types for t in ["OrderFilledEvent", "FPMM"])
            if has_required:
                print("✅ PASS: Schema contains required types")
            else:
                print("❌ FAIL: Missing required types")
                return False
        else:
            print(f"❌ FAIL: {data.get('errors', ['Unknown error'])[0]}")
            return False
    except Exception as e:
        print(f"❌ FAIL: {e}")
        return False
    
    print("\n✅ The Graph: VALIDATED")
    return True

def main():
    print(f"\n{'='*60}")
    print(f"API VALIDATION REPORT")
    print(f"Generated: {datetime.now().isoformat()}")
    print(f"{'='*60}")
    
    api_key = input("\nEnter your EtherScan API key: ").strip()
    
    if not api_key or len(api_key) < 10:
        print("❌ Invalid API key")
        return
    
    etherscan_ok = test_etherscan(api_key)
    the_graph_ok = test_the_graph()
    
    print(f"\n{'='*60}")
    print("VALIDATION SUMMARY")
    print(f"{'='*60}")
    print(f"EtherScan v2: {'✅ PASS' if etherscan_ok else '❌ FAIL'}")
    print(f"The Graph:   {'✅ PASS' if the_graph_ok else '❌ FAIL'}")
    
    if etherscan_ok and the_graph_ok:
        print("\n✅ All APIs validated successfully!")
        print("Ready for SENTINEL backend deployment.")
    else:
        print("\n❌ Some APIs failed validation.")
        print("Check your API key and network connectivity.")

if __name__ == "__main__":
    main()
```

---

## Rate Limits & Best Practices

### EtherScan v2 Rate Limits

| Tier | Requests/Second | Cost |
|------|-----------------|------|
| **Free** | 5 req/s | Free |
| **Professional** | 20 req/s | Paid |
| **Enterprise** | Unlimited | Custom |

**For SENTINEL:** Free tier (5 req/s) is sufficient for background indexing tasks.

### The Graph Rate Limits

**Hosted Service:**
- No explicit rate limit
- ~100 req/minute per IP (soft limit)
- Free forever

**Decentralized Network:**
- Based on API key tier
- Free tier: Adequate for typical usage
- Paid tiers available

### Best Practices

#### 1. Pagination for Large Result Sets

**Problem:** Querying 100,000 records at once times out.

**Solution:** Paginate with `first` + `skip`:

```python
all_events = []
skip = 0
first = 1000

while True:
    query = f"""{{
        orderFilledEvents(
            first: {first},
            skip: {skip}
        ) {{ id timestamp }}
    }}"""
    
    response = requests.post(subgraph_url, json={"query": query})
    events = response.json()["data"]["orderFilledEvents"]
    
    if not events:
        break
    
    all_events.extend(events)
    skip += first
    time.sleep(0.2)  # Respect rate limits
```

#### 2. Batch Requests

**Problem:** Making one API call per wallet is slow.

**Solution:** Query multiple wallets in one request (EtherScan supports up to 20):

```python
addresses = [addr1, addr2, addr3, ...]
addresses_csv = ",".join(addresses)

response = requests.get(
    "https://api.etherscan.io/v2/api",
    params={
        "apikey": api_key,
        "chainid": "137",
        "module": "account",
        "action": "balance",
        "address": addresses_csv
    }
)
```

#### 3. Cache Results

**Problem:** Querying the same data repeatedly wastes API quota.

**Solution:** Cache results in MongoDB with TTL indexes:

```python
# Store with 24-hour expiration
db.wallet_cache.insert_one({
    "address": wallet_address,
    "first_deposit_timestamp": int(timestamp),
    "created_at": datetime.utcnow(),
    "expires_at": datetime.utcnow() + timedelta(days=1)
})

# Create TTL index
db.wallet_cache.create_index("expires_at", expireAfterSeconds=0)
```

#### 4. Handle Partial Failures Gracefully

**Problem:** One wallet fails, entire job stops.

**Solution:** Continue processing and log failures:

```python
failed_wallets = []
for wallet in wallets:
    try:
        deposits = fetch_deposits(wallet)
        process(deposits)
    except Exception as e:
        failed_wallets.append((wallet, str(e)))
        logger.error(f"Failed to fetch deposits for {wallet}: {e}")

if failed_wallets:
    logger.warning(f"Processed {len(wallets) - len(failed_wallets)}/{len(wallets)} wallets")
```

#### 5. Add Delays Between Requests

**Problem:** Burst requests trigger rate limits.

**Solution:** Add exponential backoff:

```python
import time

def call_with_backoff(url, params, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 1s, 2s, 4s
                logger.warning(f"Retry {attempt + 1}/{max_retries} after {wait_time}s")
                time.sleep(wait_time)
            else:
                raise
```

---

## Environment Variables

### Required Variables for SENTINEL

Create `.env` file in `backend/` directory:

```dotenv
# ── ETHERSCAN v2 API ──────────────────────────────────
ETHERSCAN_API_KEY=your_free_api_key_from_etherscan.io
ETHERSCAN_API_URL=https://api.etherscan.io/v2/api

# ── THE GRAPH ─────────────────────────────────────────
POLYMARKET_SUBGRAPH_URL=https://api.thegraph.com/subgraphs/name/polymarket/polymarket

# ── POLYGON NETWORK ───────────────────────────────────
POLYGON_CHAIN_ID=137
POLYGON_RPC_URL=https://polygon-rpc.com
POLYGON_WS_URL=wss://polygon-bor-rpc.publicnode.com

# ── CONTRACT ADDRESSES (Polygon) ───────────────────────
USDC_E_ADDRESS=0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174
CTF_EXCHANGE_ADDRESS=0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E
CONDITIONAL_TOKEN_ADDRESS=0xCeAfC9B8FF2F43F2f46fdA96Eab7fFdD16DF6BA3
```

### How to Get API Keys

**EtherScan v2 API Key:**
1. Visit https://etherscan.io/apis
2. Click "Sign In" (create account if needed)
3. Create new API key
4. Select "Polygon PoS" network
5. Copy key to `.env`

**The Graph API Key (Optional):**
1. Visit https://thegraph.com/studio
2. Create new subgraph or use existing
3. Copy query URL to `.env` (includes key)
4. Or just use free hosted service without key

---

## Quick Start Integration Examples

### Python: Fetch First USDC.e Deposit

```python
import requests
from datetime import datetime

def get_first_usdc_deposit(wallet_address, api_key):
    """Get first USDC.e deposit timestamp for wallet age calculation"""
    
    url = "https://api.etherscan.io/v2/api"
    params = {
        "apikey": api_key,
        "chainid": "137",
        "module": "account",
        "action": "tokentx",
        "contractaddress": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        "address": wallet_address,
        "sort": "asc",
        "page": "1",
        "offset": "1"
    }
    
    response = requests.get(url, params=params)
    data = response.json()
    
    if data["status"] == "1" and data["result"]:
        first_transfer = data["result"][0]
        timestamp = int(first_transfer["timeStamp"])
        age_days = (datetime.now().timestamp() - timestamp) / (24 * 3600)
        
        return {
            "timestamp": timestamp,
            "age_days": age_days,
            "amount_usdc": int(first_transfer["value"]) / 1e6
        }
    else:
        return None

# Usage
deposit_info = get_first_usdc_deposit("0x...", "YOUR_API_KEY")
print(f"Wallet age: {deposit_info['age_days']} days")
```

### Python: Fetch OrderFilled Events from The Graph

```python
import requests

def fetch_orderfilledevents(asset_id, limit=1000):
    """Fetch historical OrderFilled events for asset"""
    
    url = "https://api.thegraph.com/subgraphs/name/polymarket/polymarket"
    
    query = f"""{{
        orderFilledEvents(
            first: {limit},
            where: {{ takerAssetId: "{asset_id}" }},
            orderBy: timestamp,
            orderDirection: asc
        ) {{
            id
            timestamp
            maker
            taker
            makerAssetId
            takerAssetId
            makerAmountFilled
            takerAmountFilled
            fee
        }}
    }}"""
    
    response = requests.post(
        url,
        json={"query": query},
        headers={"Content-Type": "application/json"}
    )
    
    data = response.json()
    
    if "errors" in data:
        raise Exception(f"GraphQL Error: {data['errors'][0]['message']}")
    
    return data["data"]["orderFilledEvents"]

# Usage
events = fetch_orderfilledevents("0x123abc...", limit=1000)
print(f"Fetched {len(events)} events")
```

---

## References & Documentation Links

### Official Documentation

- **EtherScan v2 API:** https://docs.etherscan.io/
- **The Graph Docs:** https://thegraph.com/docs/
- **Polygon Network:** https://polygon.technology/
- **Polymarket Subgraph (hosted):** https://api.thegraph.com/subgraphs/name/polymarket/polymarket
- **Graph Explorer:** https://thegraph.com/explorer

### Related Resources

- **SENTINEL Architecture:** See `SENTINEL_BACKEND_ARCHITECTURE_v2_REVISED.md`
- **Polygon Contract Addresses:** https://polygonscan.com/
- **GraphQL Documentation:** https://graphql.org/learn/
- **Web3.py Documentation:** https://web3py.readthedocs.io/

---

**Document Version:** 1.0  
**Last Updated:** April 2026  
**Maintained By:** SENTINEL Development Team  
**Status:** Production Ready
