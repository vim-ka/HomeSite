import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/api/client";
import Modal from "@/components/Modal";

export const SMS_CATEGORIES = ["critical", "warning", "link", "internet", "test"] as const;

interface Props {
  open: boolean;
  onClose: () => void;
  userId: number;
  username: string;
  phone: string | null;
  categories: string[];
}

function errorText(err: unknown, fallback: string): string {
  const resp = (err as { response?: { data?: { detail?: unknown } } })?.response;
  const detail = resp?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const msgs = detail.map((d) => (d as { msg?: string })?.msg).filter(Boolean);
    if (msgs.length) return msgs.join("; ");
  }
  return fallback;
}

export default function UserSmsModal({ open, onClose, userId, username, phone, categories }: Props) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [phoneValue, setPhoneValue] = useState(phone ?? "");
  const [selected, setSelected] = useState<string[]>(categories);

  const mutation = useMutation({
    mutationFn: async () => {
      await api.put(`/auth/users/${userId}/sms`, {
        phone: phoneValue.trim() === "" ? null : phoneValue,
        categories: SMS_CATEGORIES.filter((c) => selected.includes(c)),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      onClose();
    },
  });

  const toggle = (c: string) =>
    setSelected((s) => (s.includes(c) ? s.filter((x) => x !== c) : [...s, c]));

  return (
    <Modal open={open} onClose={onClose}>
        <h3 className="mb-4 text-lg font-semibold text-gray-800">
          {t("settings.smsTitle")} — {username}
        </h3>
        <div>
          <label htmlFor="sms-phone" className="block text-sm text-gray-600 mb-1">{t("settings.smsPhone")}</label>
          <input
            id="sms-phone"
            type="text"
            inputMode="tel"
            value={phoneValue}
            onChange={(e) => setPhoneValue(e.target.value)}
            placeholder="+7 900 000-00-00"
            className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none"
          />
          {mutation.isError && (
            <p className="mt-1 text-xs text-red-600">{errorText(mutation.error, t("settings.smsSaveFailed"))}</p>
          )}
          <p className="mt-1 text-xs text-gray-400">{t("settings.smsPhoneHint")}</p>
        </div>
        <fieldset className="mt-4 space-y-2">
          <legend className="text-sm text-gray-600 mb-1">{t("settings.smsCategories")}</legend>
          {SMS_CATEGORIES.map((c) => (
            <label key={c} className="flex items-center gap-2 text-sm text-gray-700">
              <input type="checkbox" checked={selected.includes(c)} onChange={() => toggle(c)} />
              {t(`settings.smsCat.${c}`)}
            </label>
          ))}
        </fieldset>
        <div className="mt-5 flex justify-end gap-3">
          <button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
            className="px-4 py-2 bg-primary-600 text-white text-sm rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors"
          >
            {t("common.save")}
          </button>
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800">
            {t("common.cancel")}
          </button>
        </div>
    </Modal>
  );
}
