export function LogoMark() {
  return (
    <div className="w-10 h-10 bg-gradient-to-br from-[#994400] to-[#b85a2a] rounded-lg flex items-center justify-center shadow-md">
      <span className="text-xl font-bold text-[#fcf9ee] leading-none">॥</span>
    </div>
  );
}

export function LogoHorizontal() {
  return (
    <div className="flex items-center gap-3">
      <LogoMark />
      <div>
        <div className="font-newsreader text-lg font-bold text-[#1c1c15]">श्रुति संवाद</div>
        <div className="text-xs font-semibold text-[#994400] tracking-wider">SHRUTI SAMVAD</div>
      </div>
    </div>
  );
}

export function LogoVertical() {
  return (
    <div className="flex flex-col items-center gap-3">
      <LogoMark />
      <div className="text-center">
        <div className="font-newsreader text-2xl font-bold text-[#1c1c15]">श्रुति संवाद</div>
        <div className="text-xs font-semibold text-[#994400] tracking-wider mt-1">SHRUTI SAMVAD</div>
        <div className="text-xs text-[#60140a] tracking-wider mt-1">INTELLIGENCE INBOX</div>
      </div>
    </div>
  );
}
