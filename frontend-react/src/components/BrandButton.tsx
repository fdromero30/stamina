import { Activity } from "lucide-react";

type BrandButtonProps = {
  onClick: () => void;
  label: string;
  className?: string;
};

export function BrandButton({ onClick, label, className = "" }: BrandButtonProps) {
  return (
    <button className={`brand-button ${className}`.trim()} onClick={onClick} aria-label={label}>
      <Activity size={24} />
      <span>Stamina</span>
    </button>
  );
}
