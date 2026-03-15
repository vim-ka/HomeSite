import { Loader2 } from "lucide-react";
import { useTranslation } from "react-i18next";

export default function LoadingSpinner() {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col items-center justify-center py-16 text-gray-400 gap-3">
      <Loader2 className="h-8 w-8 animate-spin" />
      <span className="text-sm">{t("common.loading")}</span>
    </div>
  );
}
