/** Sets document.title per page ("Report · northwind.shop · Antarctica"). */
import { useEffect } from "react";

export function useTitle(title: string) {
  useEffect(() => {
    document.title = title ? `${title} · Antarctica` : "Antarctica";
  }, [title]);
}
