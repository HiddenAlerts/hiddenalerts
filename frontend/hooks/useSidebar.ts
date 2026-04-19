'use client';

import { useCallback, useEffect, useState } from 'react';

export function useSidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  const toggleCollapse = useCallback(() => {
    setCollapsed((v) => !v);
  }, []);

  const openMobile = useCallback(() => {
    setMobileOpen(true);
  }, []);

  const closeMobile = useCallback(() => {
    setMobileOpen(false);
  }, []);

  useEffect(() => {
    if (!mobileOpen) return;

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeMobile();
    };

    document.addEventListener('keydown', onKeyDown);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = prevOverflow;
    };
  }, [mobileOpen, closeMobile]);

  return {
    collapsed,
    toggleCollapse,
    mobileOpen,
    openMobile,
    closeMobile,
  };
}
