import React from 'react';

export const WEAVE_BRAND = 'weave.';

type WeaveWordmarkProps = {
  /** Cover / login hero uses 42pt; nav and inline marks stay compact. */
  size?: 'cover' | 'nav' | 'inline';
  className?: string;
  as?: 'span' | 'h1' | 'p';
};

const SIZE_CLASS: Record<NonNullable<WeaveWordmarkProps['size']>, string> = {
  cover: 'weave-wordmark weave-wordmark--cover',
  nav: 'weave-wordmark weave-wordmark--nav',
  inline: 'weave-wordmark weave-wordmark--inline',
};

const WeaveWordmark: React.FC<WeaveWordmarkProps> = ({
  size = 'nav',
  className = '',
  as: Tag = 'span',
}) => (
  <Tag className={`${SIZE_CLASS[size]} ${className}`.trim()}>{WEAVE_BRAND}</Tag>
);

export default WeaveWordmark;
