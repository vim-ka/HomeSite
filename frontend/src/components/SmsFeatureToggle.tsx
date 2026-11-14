import { MessageSquare } from "lucide-react";
import { useTranslation } from "react-i18next";
import CollapsibleSection from "@/components/CollapsibleSection";
import { useSettingUpdate } from "@/hooks/useSettingUpdate";
import { useSmsEnabled } from "@/hooks/useSmsEnabled";

/** Infrastructure tab: the master switch of the SMS feature (tab, API and sending). */
export default function SmsFeatureToggle() {
  const { t } = useTranslation();
  const enabled = useSmsEnabled();
  const { update } = useSettingUpdate();
  return (
    <CollapsibleSection title={t("settings.smsFeature")} icon={MessageSquare} id="sms-feature">
      <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm space-y-2">
        <label className="flex items-center gap-3 text-sm text-gray-700">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => update({ sms_enabled: e.target.checked ? "1" : "0" }, true)}
            className="h-4 w-4"
          />
          {t("settings.smsFeatureOn")}
        </label>
        <p className="text-xs text-gray-500">{enabled ? t("settings.smsFeatureOnHint") : t("settings.smsFeatureOffHint")}</p>
      </div>
    </CollapsibleSection>
  );
}
