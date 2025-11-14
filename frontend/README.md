# Elis Logistics Frontend

React frontend for the Elis Logistics Manager application.

## Tech Stack

- **React 18** with TypeScript
- **Vite** for build tooling
- **Tailwind CSS** for styling
- **React Router** for navigation
- **Axios** for API calls
- **Recharts** for data visualization

## Setup

1. **Install dependencies:**
```bash
cd frontend
npm install
```

2. **Set environment variables (optional):**
Create a `.env` file:
```
VITE_API_URL=http://localhost:8000
```

3. **Run development server:**
```bash
npm run dev
```

The app will be available at http://localhost:3000

## Build

```bash
npm run build
```

The built files will be in the `dist` directory.

## Project Structure

```
src/
├── components/     # Reusable components (Layout, etc.)
├── pages/         # Page components (Dashboard, Trucks, Settlements, Repairs)
├── services/      # API service layer
└── utils/         # Utility functions
```

## Features

- **Dashboard**: Overview with KPIs and profit charts
- **Trucks**: Manage trucks (create, view)
- **Settlements**: Upload PDF settlements, view and filter by truck
- **Repairs**: Track repair expenses, filter by truck

## Development Notes

- API calls are proxied through Vite dev server (see `vite.config.ts`)
- All API endpoints are defined in `src/services/api.ts`
- Components use TypeScript for type safety
- Tailwind CSS is used for styling

