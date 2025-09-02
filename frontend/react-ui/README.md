# Sales Quote Assistant - React UI

A modern React-based user interface for the Sales Quote Assistant, built with TypeScript, Tailwind CSS, and integrated with the backend API.

## Features

- **Modern Chat Interface**: Clean, responsive chat UI with message history
- **Real-time Quote Preview**: Live quote updates as you chat with the AI
- **PDF Viewer**: Preview quotes before downloading with zoom, rotation, and navigation
- **Responsive Design**: Works seamlessly on desktop and mobile devices
- **Backend Integration**: Full integration with the FastAPI backend
- **Professional Styling**: Modern UI with Tailwind CSS

## Tech Stack

- **React 19** with TypeScript
- **Vite** for fast development and building
- **Tailwind CSS** for styling
- **Lucide React** for icons
- **React PDF** for PDF viewing
- **Axios** for API communication

## Getting Started

### Prerequisites

- Node.js 18+ (recommended 20+)
- Backend server running on `localhost:8000`

### Installation

```bash
# Install dependencies
npm install

# Start development server
npm run dev
```

The React app will be available at `http://localhost:5173`

### Building for Production

```bash
# Build the application
npm run build

# Preview the production build
npm run preview
```

## Project Structure

```
src/
├── components/
│   ├── ChatInterface.tsx    # Main chat component
│   ├── QuotePreview.tsx     # Quote preview sidebar
│   └── PDFViewer.tsx        # PDF viewer modal
├── services/
│   └── api.ts              # API service layer
├── App.tsx                 # Main application component
├── index.css              # Global styles with Tailwind
└── main.tsx               # Application entry point
```

## API Integration

The React app integrates with the following backend endpoints:

- `POST /chat` - Send chat messages
- `GET /quotes/{id}` - Get quote details
- `GET /quotes/{id}/pdf` - Download quote PDF
- `GET /healthz` - Health check

## Features in Detail

### Chat Interface
- Real-time messaging with the AI assistant
- Message history with timestamps
- Typing indicators and loading states
- Auto-scroll to latest messages
- Responsive input with auto-resize

### Quote Preview
- Real-time quote updates during conversation
- Line item details with pricing
- Total calculations
- Quote status indicators
- Direct PDF download

### PDF Viewer
- Full PDF preview in modal
- Zoom in/out controls
- Page navigation
- Rotation controls
- Download functionality

## Development

### Adding New Features

1. Create components in `src/components/`
2. Add API methods in `src/services/api.ts`
3. Update types as needed
4. Test with the backend running

### Styling

The app uses Tailwind CSS with custom components defined in `src/index.css`. Key classes:

- `.btn-primary` - Primary button styling
- `.btn-secondary` - Secondary button styling
- `.input-field` - Form input styling
- `.card` - Card container styling

## Backend Requirements

Ensure your backend server is running with:

- FastAPI server on `localhost:8000`
- CORS enabled for `localhost:5173`
- All required endpoints implemented
- Database properly seeded with demo data

## Troubleshooting

### Common Issues

1. **Backend Connection Failed**: Ensure the backend server is running on port 8000
2. **PDF Not Loading**: Check that the PDF endpoint is working and CORS is configured
3. **Styling Issues**: Ensure Tailwind CSS is properly configured

### Development Tips

- Use browser dev tools to inspect API calls
- Check the console for any error messages
- Verify backend endpoints with curl or Postman
- Use React DevTools for component debugging