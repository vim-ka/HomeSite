import { useState, useEffect, useRef, type ReactNode } from "react";
import { ChevronDown, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export default function CollapsibleSection({
  title,
  icon: Icon,
  children,
  defaultOpen = true,
  id,
  forceOpen,
  lazy,
}: {
  title: string;
  icon: LucideIcon;
  children: ReactNode;
  defaultOpen?: boolean;
  id?: string;
  forceOpen?: boolean;
  lazy?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const ref = useRef<HTMLElement>(null);

  useEffect(() => {
    if (forceOpen) {
      setOpen(true);
      ref.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [forceOpen]);

  return (
    <section id={id} ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="mb-3 flex w-full items-center gap-2 text-left"
      >
        <Icon className="h-5 w-5 text-gray-500" />
        <h3 className="text-lg font-semibold text-gray-700">{title}</h3>
        <ChevronDown
          className={cn(
            "ml-auto h-5 w-5 text-gray-400 transition-transform duration-200",
            open && "rotate-180",
          )}
        />
      </button>
      <div
        className={cn(
          "grid transition-all duration-200 ease-in-out",
          open ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0",
        )}
      >
        <div className="overflow-hidden">{(!lazy || open) && children}</div>
      </div>
    </section>
  );
}
