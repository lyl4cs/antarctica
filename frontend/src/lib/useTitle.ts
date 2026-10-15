/** Sets document.title per page ("Report · northwind.shop · sn0wy"). */
import { useEffect } from "react";

export function useTitle(title: string) {
  useEffect(() => {
    document.title = title ? `${title} · sn0wy` : "sn0wy";
  }, [title]);
}
