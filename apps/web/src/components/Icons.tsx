import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

function Svg({ children, className = "size-5", ...props }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
      {...props}
    >
      {children}
    </svg>
  );
}

export function IconHome(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M4 11.2 12 4l8 7.2V20a1 1 0 0 1-1 1h-5v-6H10v6H5a1 1 0 0 1-1-1z" />
    </Svg>
  );
}

export function IconFollowing(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="8" r="3.2" />
      <path d="M5.5 19.2c.7-3 3.2-4.7 6.5-4.7s5.8 1.7 6.5 4.7" />
    </Svg>
  );
}

export function IconFriends(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="9" cy="8" r="2.8" />
      <path d="M3.8 19c.6-2.6 2.6-4.1 5.2-4.1 2.6 0 4.6 1.5 5.2 4.1" />
      <circle cx="16.5" cy="8.5" r="2.2" />
      <path d="M15 14.2c2.1.2 3.7 1.5 4.3 3.8" />
    </Svg>
  );
}

export function IconInbox(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M4 7.5 12 13l8-5.5" />
      <rect x="4" y="5" width="16" height="14" rx="2" />
    </Svg>
  );
}

export function IconPlus(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M12 5v14M5 12h14" />
    </Svg>
  );
}

export function IconPlusBox(props: IconProps) {
  return (
    <Svg {...props}>
      <rect x="4" y="4" width="16" height="16" rx="3" />
      <path d="M12 8v8M8 12h8" />
    </Svg>
  );
}

export function IconProfile(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="8" r="3.2" />
      <path d="M5 19.5c.8-3.2 3.4-5 7-5s6.2 1.8 7 5" />
    </Svg>
  );
}

export function IconMore(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="6" cy="12" r="1.3" fill="currentColor" stroke="none" />
      <circle cx="12" cy="12" r="1.3" fill="currentColor" stroke="none" />
      <circle cx="18" cy="12" r="1.3" fill="currentColor" stroke="none" />
    </Svg>
  );
}

export function IconHeart({ filled, ...props }: IconProps & { filled?: boolean }) {
  return (
    <Svg {...props} fill={filled ? "currentColor" : "none"}>
      <path d="M12 20s-7-4.4-7-9.2A3.8 3.8 0 0 1 12 8a3.8 3.8 0 0 1 7 2.8C19 15.6 12 20 12 20z" />
    </Svg>
  );
}

export function IconComment(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M5 6.5A2.5 2.5 0 0 1 7.5 4h9A2.5 2.5 0 0 1 19 6.5v7A2.5 2.5 0 0 1 16.5 16H10l-4.5 3.2V16H7.5A2.5 2.5 0 0 1 5 13.5z" />
    </Svg>
  );
}

export function IconShare(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M14 6.5 20 12l-6 5.5" />
      <path d="M20 12H10.5C7.5 12 5 14.2 5 17.2V19" />
    </Svg>
  );
}

export function IconRotate(props: IconProps) {
  return (
    <Svg {...props}>
      <rect x="7" y="4" width="10" height="16" rx="2" />
      <path d="M4 9.5 7 7M4 9.5 7 12M20 14.5 17 12M20 14.5 17 17" />
    </Svg>
  );
}

export function IconMusic(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M9 18.5a2.5 2.5 0 1 1-2.2-2.48V8.2L19 5.5v8.2" />
      <circle cx="16.5" cy="15.5" r="2.5" />
    </Svg>
  );
}

export function IconChevronUp(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M6 14.5 12 8.5l6 6" />
    </Svg>
  );
}

export function IconChevronDown(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M6 9.5 12 15.5l6-6" />
    </Svg>
  );
}

export const NAV_ICONS = {
  home: IconHome,
  following: IconFollowing,
  friends: IconFriends,
  inbox: IconInbox,
  plus: IconPlusBox,
  profile: IconProfile,
} as const;

export type NavIconName = keyof typeof NAV_ICONS;
