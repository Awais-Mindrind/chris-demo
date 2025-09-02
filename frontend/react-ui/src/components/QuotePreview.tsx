import React, { useState } from "react";
import {
  FileText,
  Download,
  Eye,
  X,
  DollarSign,
  Package,
  User,
} from "lucide-react";
import { QuoteData } from "../services/api";
import PDFViewer from "./PDFViewer";

interface QuotePreviewProps {
  quoteData?: QuoteData;
  pdfUrl?: string;
}

const QuotePreview: React.FC<QuotePreviewProps> = ({ quoteData, pdfUrl }) => {
  const [showPdfViewer, setShowPdfViewer] = useState(false);

  const calculateLineTotal = (line: any) => {
    const unitPrice = line.unit_price || 0;
    const quantity = line.qty || 0;
    const discount = line.discount_pct || 0;
    const subtotal = unitPrice * quantity;
    const discountAmount = subtotal * discount;
    return subtotal - discountAmount;
  };

  const calculateQuoteTotal = () => {
    if (!quoteData?.lines) return 0;
    return quoteData.lines.reduce(
      (total, line) => total + calculateLineTotal(line),
      0
    );
  };

  const handleDownloadPdf = async () => {
    if (!quoteData?.id) return;

    try {
      const response = await fetch(
        `http://localhost:8000/quotes/${quoteData.id}/pdf`
      );
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `quote-${quoteData.id}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error("Error downloading PDF:", error);
    }
  };

  if (!quoteData) {
    return (
      <div className="h-full flex flex-col">
        <div className="p-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900 flex items-center">
            <FileText className="w-5 h-5 mr-2" />
            Quote Preview
          </h3>
        </div>
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="text-center">
            <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <FileText className="w-8 h-8 text-gray-400" />
            </div>
            <h4 className="text-lg font-medium text-gray-900 mb-2">
              No Quote Yet
            </h4>
            <p className="text-gray-500 max-w-sm">
              Start a conversation to create a quote. I'll help you build a
              professional quote with your customer's information and product
              details.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-900 flex items-center">
            <FileText className="w-5 h-5 mr-2" />
            Quote #{quoteData.id}
          </h3>
          <div className="flex items-center space-x-2">
            {pdfUrl && (
              <>
                <button
                  onClick={() => setShowPdfViewer(true)}
                  className="btn-secondary flex items-center text-sm px-3 py-1.5"
                >
                  <Eye className="w-4 h-4 mr-1" />
                  Preview
                </button>
                <button
                  onClick={handleDownloadPdf}
                  className="btn-primary flex items-center text-sm px-3 py-1.5"
                >
                  <Download className="w-4 h-4 mr-1" />
                  Download
                </button>
              </>
            )}
          </div>
        </div>
        <div className="mt-2 flex items-center text-sm text-gray-600">
          <span
            className={`px-2 py-1 rounded-full text-xs font-medium ${
              quoteData.status === "draft"
                ? "bg-yellow-100 text-yellow-800"
                : quoteData.status === "sent"
                ? "bg-blue-100 text-blue-800"
                : "bg-green-100 text-green-800"
            }`}
          >
            {quoteData.status.charAt(0).toUpperCase() +
              quoteData.status.slice(1)}
          </span>
        </div>
      </div>

      {/* Quote Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {/* Customer Info */}
        <div className="mb-6">
          <h4 className="text-sm font-medium text-gray-900 mb-3 flex items-center">
            <User className="w-4 h-4 mr-2" />
            Bill To
          </h4>
          <div className="bg-gray-50 rounded-lg p-3">
            <p className="font-medium text-gray-900">
              {quoteData.account_name}
            </p>
          </div>
        </div>

        {/* Line Items */}
        <div className="mb-6">
          <h4 className="text-sm font-medium text-gray-900 mb-3 flex items-center">
            <Package className="w-4 h-4 mr-2" />
            Line Items
          </h4>
          <div className="space-y-3">
            {quoteData.lines.map((line, index) => (
              <div key={index} className="bg-gray-50 rounded-lg p-3">
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <p className="font-medium text-gray-900">{line.sku_name}</p>
                    <p className="text-sm text-gray-500">
                      SKU: {line.sku_code}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="font-medium text-gray-900">
                      ${calculateLineTotal(line).toFixed(2)}
                    </p>
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-4 text-sm text-gray-600">
                  <div>
                    <span className="font-medium">Qty:</span> {line.qty}
                  </div>
                  <div>
                    <span className="font-medium">Price:</span> $
                    {line.unit_price.toFixed(2)}
                  </div>
                  <div>
                    <span className="font-medium">Discount:</span>{" "}
                    {(line.discount_pct * 100).toFixed(1)}%
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Total */}
        <div className="border-t border-gray-200 pt-4">
          <div className="flex justify-between items-center">
            <span className="text-lg font-semibold text-gray-900 flex items-center">
              <DollarSign className="w-5 h-5 mr-1" />
              Total
            </span>
            <span className="text-2xl font-bold text-primary-600">
              ${calculateQuoteTotal().toFixed(2)}
            </span>
          </div>
        </div>
      </div>

      {/* PDF Viewer Modal */}
      {showPdfViewer && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-[90vw] h-[90vh] flex flex-col">
            <div className="flex items-center justify-between p-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">
                Quote #{quoteData.id} - PDF Preview
              </h3>
              <button
                onClick={() => setShowPdfViewer(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-6 h-6" />
              </button>
            </div>
            <div className="flex-1">
              <PDFViewer pdfUrl={pdfUrl} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default QuotePreview;
