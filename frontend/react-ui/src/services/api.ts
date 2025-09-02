import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export interface QuoteLine {
  sku_name: string;
  sku_code: string;
  qty: number;
  unit_price: number;
  discount_pct: number;
}

export interface QuoteData {
  id: number;
  status: string;
  account_name: string;
  lines: QuoteLine[];
}

export interface ChatResponse {
  response: string;
  session_id: string;
  quote_data?: QuoteData;
  pdf_url?: string;
  success: boolean;
  error?: string;
}

export interface CreateQuoteRequest {
  account_id: number;
  pricebook_id: number;
  lines: Array<{
    sku_id: number;
    qty: number;
    unit_price?: number;
    discount_pct?: number;
  }>;
  idempotency_key?: string;
}

export interface Account {
  id: number;
  name: string;
  domain?: string;
  confidence_score: number;
}

export interface Pricebook {
  id: number;
  name: string;
  currency: string;
  is_default: boolean;
}

export interface Sku {
  id: number;
  code: string;
  name: string;
  unit_price: number;
  pricebook_id: number;
  attributes?: Record<string, any>;
}

class ApiService {
  async sendChatMessage(message: string, sessionId?: string): Promise<ChatResponse> {
    const response = await api.post('/chat', {
      message,
      session_id: sessionId,
    });
    return response.data;
  }

  async createQuote(quoteData: CreateQuoteRequest): Promise<{ quote_id: number }> {
    const response = await api.post('/actions/create_quote', quoteData);
    return response.data;
  }

  async getQuote(quoteId: number): Promise<QuoteData> {
    const response = await api.get(`/quotes/${quoteId}`);
    return response.data;
  }

  async getQuotePdf(quoteId: number): Promise<Blob> {
    const response = await api.get(`/quotes/${quoteId}/pdf`, {
      responseType: 'blob',
    });
    return response.data;
  }

  async findAccounts(query: string): Promise<Account[]> {
    const response = await api.post('/tools/find_account', { query });
    return response.data.candidates || [];
  }

  async listPricebooks(): Promise<Pricebook[]> {
    const response = await api.post('/tools/list_pricebooks', {});
    return response.data;
  }

  async listSkus(filters?: {
    name?: string;
    code?: string;
    pricebook_id?: number;
  }): Promise<Sku[]> {
    const response = await api.post('/tools/list_skus', { filters });
    return response.data;
  }

  async healthCheck(): Promise<{ status: string }> {
    const response = await api.get('/healthz');
    return response.data;
  }
}

export const apiService = new ApiService();
export default apiService;
