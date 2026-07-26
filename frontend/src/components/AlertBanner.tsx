import { AlertTriangle, Info } from 'lucide-react';

interface Props {
  message: string;
  type: 'warning' | 'info';
}

export function AlertBanner({ message, type }: Props) {
  const isWarning = type === 'warning';
  return (
    <div className={`p-4 rounded-lg flex items-center gap-3 border ${isWarning ? 'bg-yellow-50 border-yellow-200 text-yellow-800' : 'bg-blue-50 border-blue-200 text-blue-800'}`}>
      {isWarning ? <AlertTriangle className="w-5 h-5 text-yellow-600" /> : <Info className="w-5 h-5 text-blue-600" />}
      <span className="font-medium">{message}</span>
    </div>
  );
}
