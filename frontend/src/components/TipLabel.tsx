import { useState, useRef, useEffect } from "react";
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
  const tipRef = useRef<HTMLDivElement>(null);
  const btnRef = useRef<HTMLButtonElement>(null);

  // Close on click outside
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

  return (
    <label className={`flex items-center gap-1 ${className}`}>
      <span>{text}</span>
      {tip && (
        <span className="relative inline-flex">
          <button
            ref={btnRef}
            type="button"
            onMouseEnter={() => setShow(true)}
            onMouseLeave={() => setShow(false)}
            onClick={() => setShow(!show)}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <HelpCircle className="h-3.5 w-3.5" />
          </button>
          {show && (
            <div
              ref={tipRef}
              className="absolute left-5 bottom-0 z-50 w-64 rounded-lg border border-gray-200 bg-white p-2.5 text-xs text-gray-600 shadow-lg"
            >
              {tip}
            </div>
          )}
        </span>
      )}
    </label>
  );
}
