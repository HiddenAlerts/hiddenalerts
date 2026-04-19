'use client';

import { cn } from '@/lib/utils';
import React, { useState } from 'react';

import type { AvatarProps } from './Avatar.types';
import { avatarImgSizeMap, avatarRadiusMap, avatarSizeMap } from './avatarData';

/** Served from `public/images/user-avatar.png` */
const DEFAULT_AVATAR_SRC = '/images/user-avatar.png';

type AvatarImageProps = {
  alt?: string;
  canonicalSrc: string;
  imgStyles?: string;
  avatarImgSize: { width: number; height: number };
};

function AvatarImage({
  alt,
  canonicalSrc,
  imgStyles,
  avatarImgSize,
}: AvatarImageProps) {
  const [useFallback, setUseFallback] = useState(false);
  const src = useFallback ? DEFAULT_AVATAR_SRC : canonicalSrc;

  return (
    // Remount when the requested image changes so error state resets.
    <img
      key={canonicalSrc}
      alt={alt || 'avatar'}
      className={cn('aspect-square h-full w-full object-cover', imgStyles)}
      height={avatarImgSize.height}
      width={avatarImgSize.width}
      src={src}
      onError={() => setUseFallback(true)}
    />
  );
}

const Avatar: React.FC<AvatarProps> = ({
  className,
  alt,
  src,
  size = 'xl',
  imgStyles,
  type = 'rounded',
}) => {
  const avatarSize = avatarSizeMap[size];
  const canonicalSrc = src ?? DEFAULT_AVATAR_SRC;

  const avatarRadius =
    type === 'rectangle' ? avatarRadiusMap[size] : 'rounded-full';
  const avatarImgSize = avatarImgSizeMap[size];

  return (
    <div
      className={cn(
        'relative flex h-full w-full shrink-0 items-center justify-center overflow-hidden bg-neutral-100',
        avatarSize,
        className,
        avatarRadius,
      )}
    >
      <AvatarImage
        alt={alt}
        canonicalSrc={canonicalSrc}
        imgStyles={imgStyles}
        avatarImgSize={avatarImgSize}
      />
    </div>
  );
};

export default Avatar;
