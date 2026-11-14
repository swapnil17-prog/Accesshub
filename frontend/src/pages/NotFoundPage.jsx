import { SearchIcon } from '../components/icons';
import { ErrorScreen } from './ForbiddenPage';

export default function NotFoundPage() {
  return (
    <ErrorScreen
      icon={SearchIcon}
      code="404"
      title="Page not found"
      description="The page you're looking for doesn't exist or has moved."
    />
  );
}
