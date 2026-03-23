import { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { HelpCircle } from "lucide-react";

export default function TipLabel({
  text,
  tip,
  className = "",
}: {
  text: string;
  tip?: string;
  className?: string;
}) {
  const [show, setShow] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0 });
  const tipRef = useRef<HTMLDivElement>(null);
  const btnRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!show) return;
    const handler = (e: MouseEvent) => {
      if (
        tipRef.current &&
        !tipRef.current.contains(e.target as Node) &&
        btnRef.current &&
        !btnRef.current.contains(e.target as Node)
      ) {
        setShow(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [show]);

  const open = () => {
    if (btnRef.current) {
      const r = btnRef.current.getBoundingClientRect();
      setPos({ top: r.bottom + window.scrollY + 4, left: r.left + window.scrollX });
    }
    setShow(true);
  };

  return (
    <label className={`flex items-center gap-1 ${className}`}>
      <span>{text}</span>
      {tip && (
        <>
          <button
            ref={btnRef}
            type="button"
            onMouseEnter={open}
            onMouseLeave={() => setShow(false)}
            onClick={() => (show ? setShow(false) : open())}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <HelpCircle className="h-3.5 w-3.5" />
          </button>
          {show &&
            createPortal(
              <div
                ref={tipRef}
                style={{ top: pos.top, left: pos.left }}
                className="fixed z-[9999] w-64 rounded-lg border border-gray-200 bg-white p-2.5 text-xs text-gray-600 shadow-lg"
              >
                {tip}
              </div>,
              document.body,
            )}
        </>
      )}
    </label>
  );
}
