type P = { className?: string };
const base = "h-4 w-4";

const S = ({
  children,
  className,
  vb = "0 0 24 24",
}: {
  children: React.ReactNode;
  className?: string;
  vb?: string;
}) => (
  <svg
    viewBox={vb}
    fill="none"
    stroke="currentColor"
    strokeWidth={1.25}
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className ?? base}
  >
    {children}
  </svg>
);

export const IconPlay = (p: P) => (
  <S {...p}>
    <path d="M8 5.5v13l11-6.5z" fill="currentColor" stroke="none" />
  </S>
);
export const IconPause = (p: P) => (
  <S {...p}>
    <rect x="7" y="5" width="3.4" height="14" rx="1" fill="currentColor" stroke="none" />
    <rect x="13.6" y="5" width="3.4" height="14" rx="1" fill="currentColor" stroke="none" />
  </S>
);
export const IconStart = (p: P) => (
  <S {...p}>
    <path d="M18 5.5v13L8 12z" fill="currentColor" stroke="none" />
    <path d="M6 5v14" />
  </S>
);
export const IconEnd = (p: P) => (
  <S {...p}>
    <path d="M6 5.5v13L16 12z" fill="currentColor" stroke="none" />
    <path d="M18 5v14" />
  </S>
);
export const IconScissors = (p: P) => (
  <S {...p}>
    <circle cx="6" cy="18" r="2.2" />
    <circle cx="6" cy="6" r="2.2" />
    <path d="M7.9 7.6 20 18M7.9 16.4 20 6" />
  </S>
);
export const IconSparkle = (p: P) => (
  <S {...p}>
    <path d="M12 3.2 13.6 8 18.4 9.6 13.6 11.2 12 16 10.4 11.2 5.6 9.6 10.4 8z" />
    <path d="M18.4 15.6l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7z" />
  </S>
);
export const IconLayers = (p: P) => (
  <S {...p}>
    <path d="M12 3.5 20 8l-8 4.5L4 8z" />
    <path d="M4 12.5 12 17l8-4.5" />
    <path d="M4 16.5 12 21l8-4.5" />
  </S>
);
export const IconMusic = (p: P) => (
  <S {...p}>
    <circle cx="7" cy="17.5" r="2.6" />
    <circle cx="18" cy="15.5" r="2.6" />
    <path d="M9.6 17.5V7l11-2.4v10.9" />
  </S>
);
export const IconType = (p: P) => (
  <S {...p}>
    <path d="M5 6h14M12 6v13M9 19h6" />
  </S>
);
export const IconChart = (p: P) => (
  <S {...p}>
    <path d="M4 19V5M20 19H4" />
    <path d="M7.5 15.5v-3M11.5 15.5v-7M15.5 15.5v-4.5M19 15.5V8" />
  </S>
);
export const IconDownload = (p: P) => (
  <S {...p}>
    <path d="M12 4v10m0 0 3.6-3.6M12 14l-3.6-3.6" />
    <path d="M4.5 17.5v1.2a1.8 1.8 0 0 0 1.8 1.8h11.4a1.8 1.8 0 0 0 1.8-1.8v-1.2" />
  </S>
);
export const IconUndo = (p: P) => (
  <S {...p}>
    <path d="M4 9h9.5a5 5 0 0 1 0 10H8" />
    <path d="M4 9l4-4M4 9l4 4" />
  </S>
);
export const IconRedo = (p: P) => (
  <S {...p}>
    <path d="M20 9h-9.5a5 5 0 0 0 0 10H16" />
    <path d="M20 9l-4-4M20 9l-4 4" />
  </S>
);
export const IconGrid = (p: P) => (
  <S {...p}>
    <rect x="4" y="4" width="16" height="16" rx="1.6" />
    <path d="M9.3 4v16M14.7 4v16M4 9.3h16M4 14.7h16" />
  </S>
);
export const IconLoop = (p: P) => (
  <S {...p}>
    <path d="M4.5 12a5.5 5.5 0 0 1 5.5-5.5h9" />
    <path d="M16.5 3.5 19.5 6.5 16.5 9.5" />
    <path d="M19.5 12a5.5 5.5 0 0 1-5.5 5.5H5" />
    <path d="M7.5 14.5 4.5 17.5 7.5 20.5" />
  </S>
);
export const IconVolume = (p: P) => (
  <S {...p}>
    <path d="M4 10v4h3l4 3.5v-11L7 10z" />
    <path d="M14.5 9.5a3.6 3.6 0 0 1 0 5M17 7a7 7 0 0 1 0 10" />
  </S>
);
export const IconMagnet = (p: P) => (
  <S {...p}>
    <path d="M6 4v7a6 6 0 0 0 12 0V4h-4v7a2 2 0 0 1-4 0V4z" />
    <path d="M6 8h4M14 8h4" />
  </S>
);
export const IconCpu = (p: P) => (
  <S {...p}>
    <rect x="7" y="7" width="10" height="10" rx="1.6" />
    <path d="M10 3.5v2M14 3.5v2M10 18.5v2M14 18.5v2M3.5 10h2M3.5 14h2M18.5 10h2M18.5 14h2" />
  </S>
);
export const IconCheck = (p: P) => (
  <S {...p}>
    <path d="M5 12.8 9.6 17.2 19 7" />
  </S>
);
export const IconAlert = (p: P) => (
  <S {...p}>
    <path d="M12 4.5 21 19.5H3z" />
    <path d="M12 10v4M12 16.6v.6" />
  </S>
);
export const IconClock = (p: P) => (
  <S {...p}>
    <circle cx="12" cy="12" r="8" />
    <path d="M12 7.5V12l3 2" />
  </S>
);
export const IconFlame = (p: P) => (
  <S {...p}>
    <path d="M12 3s5.5 4.2 5.5 9a5.5 5.5 0 0 1-11 0c0-2.4 1.3-4 2.4-5.2" />
    <path d="M12 20a2.6 2.6 0 0 0 2.6-2.6c0-2-2.6-3.4-2.6-3.4s-2.6 1.4-2.6 3.4A2.6 2.6 0 0 0 12 20z" />
  </S>
);
export const IconBookmark = (p: P) => (
  <S {...p}>
    <path d="M6.5 4h11v16l-5.5-4-5.5 4z" />
  </S>
);
export const IconComment = (p: P) => (
  <S {...p}>
    <path d="M4.5 6.5A2 2 0 0 1 6.5 4.5h11a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H10l-5.5 4z" />
  </S>
);
export const IconSend = (p: P) => (
  <S {...p}>
    <path d="M20 12 4 5l3 7-3 7z" />
    <path d="M7 12h13" />
  </S>
);
export const IconEye = (p: P) => (
  <S {...p}>
    <path d="M2.8 12S6 6.5 12 6.5 21.2 12 21.2 12 18 17.5 12 17.5 2.8 12 2.8 12z" />
    <circle cx="12" cy="12" r="2.6" />
  </S>
);
export const IconSettings = (p: P) => (
  <S {...p}>
    <circle cx="12" cy="12" r="3" />
    <path d="M12 3.5v2.2M12 18.3v2.2M4.6 7.8l1.9 1.1M17.5 15.1l1.9 1.1M4.6 16.2l1.9-1.1M17.5 8.9l1.9-1.1" />
  </S>
);
export const IconPlus = (p: P) => (
  <S {...p}>
    <path d="M12 5.5v13M5.5 12h13" />
  </S>
);
export const IconChevron = (p: P) => (
  <S {...p}>
    <path d="M9 6l6 6-6 6" />
  </S>
);
export const IconWand = (p: P) => (
  <S {...p}>
    <path d="M5 19 16.5 7.5" />
    <path d="M14.8 5.8 18.2 9.2" />
    <path d="M19 13.5v.01M20.5 8v.01M15 4v.01M8 5.5v.01M5 11v.01" />
  </S>
);
export const IconCrop = (p: P) => (
  <S {...p}>
    <path d="M7 3v14h14" />
    <path d="M3 7h14v14" />
  </S>
);
export const IconLock = (p: P) => (
  <S {...p}>
    <rect x="5.5" y="10.5" width="13" height="9.5" rx="1.6" />
    <path d="M8.5 10.5V8a3.5 3.5 0 0 1 7 0v2.5" />
  </S>
);
export const IconShare = (p: P) => (
  <S {...p}>
    <circle cx="6" cy="12" r="2.4" />
    <circle cx="18" cy="6.5" r="2.4" />
    <circle cx="18" cy="17.5" r="2.4" />
    <path d="M8.2 10.9 15.8 7.5M8.2 13.1l7.6 3.4" />
  </S>
);


export const IconPin = ({ className, filled }: P & { filled?: boolean }) => (
  <S className={className}>
    <path
      d="M16 4v4l2 3v2h-5v7l-1 1-1-1v-7H6v-2l2-3V4c0-.6.4-1 1-1h6c.6 0 1 .4 1 1z"
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
    />
  </S>
);

export const IconRefresh = (p: P) => (
  <S {...p}>
    <path d="M21 12a9 9 0 0 1-15.3 6.36M3 12a9 9 0 0 1 15.3-6.36" />
    <path d="M3 17v4h4M21 7V3h-4" />
  </S>
);

export const IconTrash = (p: P) => (
  <S {...p}>
    <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M10 11v6M14 11v6" />
  </S>
);

export const IconFolder = (p: P) => (
  <S {...p}>
    <path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z" />
  </S>
);

export const IconMenu = (p: P) => (
  <S {...p}>
    <line x1="3" y1="6" x2="21" y2="6" />
    <line x1="3" y1="12" x2="21" y2="12" />
    <line x1="3" y1="18" x2="21" y2="18" />
  </S>
);

export const IconClose = (p: P) => (
  <S {...p}>
    <line x1="18" y1="6" x2="6" y2="18" />
    <line x1="6" y1="6" x2="18" y2="18" />
  </S>
);

export const IconCopy = (p: P) => (
  <S {...p}>
    <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
  </S>
);

export const IconMic = (p: P) => (
  <S {...p}>
    <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
    <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
    <line x1="12" x2="12" y1="19" y2="22" />
  </S>
);



