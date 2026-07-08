import { Link } from "react-router-dom";
import { AlertTriangle, ArrowLeft } from "lucide-react";

export function NotFound() {
  return (
    <div className="page-content not-found">
      <div className="not-found-content">
        <AlertTriangle size={48} aria-hidden="true" />
        <h1>Page Not Found</h1>
        <p>The page you are looking for does not exist.</p>
        <Link to="/" className="action-button">
          <ArrowLeft size={18} />
          Back to Dashboard
        </Link>
      </div>
    </div>
  );
}
