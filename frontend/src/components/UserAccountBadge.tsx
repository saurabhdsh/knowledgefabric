import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { userInitials } from '../utils/authStorage';

interface UserAccountBadgeProps {
  compact?: boolean;
}

const UserAccountBadge: React.FC<UserAccountBadgeProps> = ({ compact = false }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const initials = userInitials(user);
  const displayName = user?.display_name || user?.username || 'User';

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  if (compact) {
    return (
      <div className="flex items-center gap-2 shrink-0 rounded-lg border border-[rgba(148,163,184,0.16)] bg-white/[0.03] px-2 py-1.5">
        <div className="h-7 w-7 rounded-md bg-gradient-to-br from-cyan-400 to-violet-500 text-[10px] font-semibold text-white flex items-center justify-center">
          {initials}
        </div>
        <span className="text-xs text-[#e8edf4] font-medium truncate max-w-[88px]">{displayName}</span>
        <button
          type="button"
          onClick={handleLogout}
          className="text-[10px] uppercase tracking-[0.12em] text-[#8b9cb0] hover:text-[#e8edf4] whitespace-nowrap"
        >
          Logout
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 rounded-lg border border-[rgba(148,163,184,0.16)] bg-white/[0.03] px-2.5 py-1.5 shrink-0">
      <div className="h-7 w-7 rounded-md bg-gradient-to-br from-cyan-400 to-violet-500 text-[10px] font-semibold text-white flex items-center justify-center">
        {initials}
      </div>
      <div className="leading-tight min-w-0 hidden sm:block">
        <div className="text-xs text-[#e8edf4] font-medium truncate max-w-[140px]">{displayName}</div>
        <div className="text-[10px] uppercase tracking-[0.14em] text-[#8b9cb0]">Signed in</div>
      </div>
      <button
        type="button"
        onClick={handleLogout}
        className="ml-1 text-[10px] uppercase tracking-[0.12em] text-[#8b9cb0] hover:text-[#e8edf4] whitespace-nowrap"
      >
        Logout
      </button>
    </div>
  );
};

export default UserAccountBadge;
