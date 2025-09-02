import React, { useState } from "react";
import { MessageSquare, FileText, Wifi, WifiOff } from "lucide-react";
import ChatInterface from "./components/ChatInterface";
import QuotePreview from "./components/QuotePreview";
import { QuoteData } from "./services/api";
import { apiService } from "./services/api";

function App() {
  const [currentQuote, setCurrentQuote] = useState<QuoteData | undefined>();
  const [currentPdfUrl, setCurrentPdfUrl] = useState<string | undefined>();
  const [isBackendConnected, setIsBackendConnected] = useState<boolean | null>(
    null
  );

  // Check backend connection on mount
  React.useEffect(() => {
    const checkConnection = async () => {
      try {
        await apiService.healthCheck();
        setIsBackendConnected(true);
      } catch (error) {
        console.error("Backend connection failed:", error);
        setIsBackendConnected(false);
      }
    };

    checkConnection();
    // Check connection every 30 seconds
    const interval = setInterval(checkConnection, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleQuoteUpdate = (quoteData: QuoteData) => {
    setCurrentQuote(quoteData);
  };

  const handlePdfUpdate = (pdfUrl: string) => {
    setCurrentPdfUrl(pdfUrl);
  };

  if (isBackendConnected === false) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <WifiOff className="w-8 h-8 text-red-600" />
          </div>
          <h2 className="text-xl font-semibold text-gray-900 mb-2">
            Backend Connection Failed
          </h2>
          <p className="text-gray-600 mb-4">
            Unable to connect to the backend server at localhost:8000
          </p>
          <p className="text-sm text-gray-500">
            Please ensure the backend server is running and try refreshing the
            page.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center space-x-3">
              <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
                <MessageSquare className="w-5 h-5 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-semibold text-gray-900">
                  Sales Quote Assistant
                </h1>
                <p className="text-sm text-gray-500">
                  AI-powered quote creation and management
                </p>
              </div>
            </div>

            <div className="flex items-center space-x-4">
              {isBackendConnected && (
                <div className="flex items-center text-sm text-green-600">
                  <Wifi className="w-4 h-4 mr-1" />
                  Connected
                </div>
              )}
              <div className="text-sm text-gray-500">
                Demo 1 - Quote Creation Agent
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-[calc(100vh-8rem)]">
          {/* Chat Interface - Takes 2/3 of the width on large screens */}
          <div className="lg:col-span-2">
            <div className="card h-full">
              <ChatInterface
                onQuoteUpdate={handleQuoteUpdate}
                onPdfUpdate={handlePdfUpdate}
              />
            </div>
          </div>

          {/* Quote Preview - Takes 1/3 of the width on large screens */}
          <div className="lg:col-span-1">
            <div className="card h-full">
              <QuotePreview quoteData={currentQuote} pdfUrl={currentPdfUrl} />
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between text-sm text-gray-500">
            <div>Built with React, TypeScript, and Tailwind CSS</div>
            <div>Powered by LangChain + Google Gemini AI</div>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;
