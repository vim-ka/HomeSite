import { useState, useRef, useEffect, useLayoutEffect } from "react";

const GAP = 4;      // between the "?" and the tip
const MARGIN = 8;   // the tip keeps this far from the window edges
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
  const [anchor, setAnchor] = useState<DOMRect | null>(null);
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
    // the tip is fixed to the window: on scroll it would drift off its "?" — close it
    const close = () => setShow(false);
    document.addEventListener("mousedown", handler);
    window.addEventListener("scroll", close, true);
    return () => {
      document.removeEventListener("mousedown", handler);
      window.removeEventListener("scroll", close, true);
    };
  }, [show]);

  // `fixed` positions are window coordinates (no scroll offset). Below the "?" if it fits, above otherwise;
  // never past the right edge.
  useLayoutEffect(() => {
    if (!show || !anchor || !tipRef.current) return;
    const { offsetWidth: w, offsetHeight: h } = tipRef.current;
    const below = anchor.bottom + GAP;
    const top = below + h <= window.innerHeight - MARGIN ? below : Math.max(MARGIN, anchor.top - GAP - h);
    const left = Math.max(MARGIN, Math.min(anchor.left, window.innerWidth - MARGIN - w));
    setPos({ top, left });
  }, [show, anchor]);

  const open = () => {
    if (btnRef.current) setAnchor(btnRef.current.getBoundingClientRect());
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
