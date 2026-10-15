/** Sets document.title per page ("Report · northwind.shop · Sn0wy"). */
import { useEffect } from "react";

export function useTitle(title: string) {
  useEffect(() => {
    document.title = title ? `${title} · Sn0wy` : "Sn0wy";
  }, [title]);
}
