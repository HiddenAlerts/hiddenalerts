'use client';

import { cn } from '@/lib/utils';
import React, { useEffect, useState } from 'react';

import type { AvatarProps } from './Avatar.types';
import { avatarImgSizeMap, avatarRadiusMap, avatarSizeMap } from './avatarData';

/** Served from `public/images/user-avatar.png` */
const DEFAULT_AVATAR_SRC = '/images/user-avatar.png';

const Avatar: React.FC<AvatarProps> = ({
  className,
  alt,
  src,
  size = 'xl',
  imgStyles,
  type = 'rounded',
}) => {
  const avatarSize = avatarSizeMap[size];
  const [imgSrc, setImgSrc] = useState<string>(src ?? DEFAULT_AVATAR_SRC);
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    if (src) {
      setImgSrc(src);
      setHasError(false);
    } else {
      setImgSrc(DEFAULT_AVATAR_SRC);
      setHasError(false);
    }
  }, [src]);

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
      <img
        alt={alt || 'avatar'}
        className={cn('aspect-square h-full w-full object-cover', imgStyles)}
        height={avatarImgSize.height}
        width={avatarImgSize.width}
        src={imgSrc}
        onError={() => {
          if (!hasError) {
            setImgSrc(DEFAULT_AVATAR_SRC);
            setHasError(true);
          }
        }}
      />
    </div>
  );
};

export default Avatar;
