import type { AvatarSize } from './avatarData';

export interface AvatarProps {
  className?: string;
  size?: AvatarSize;
  alt?: string;
  src?: string;
  imgStyles?: string;
  type?: 'rounded' | 'rectangle';
}
