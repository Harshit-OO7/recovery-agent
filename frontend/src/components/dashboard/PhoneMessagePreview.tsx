import React from 'react';
import { ExternalLink, CheckCheck, Wifi, Battery, Signal } from 'lucide-react';
import { cn } from '@/utils/cn';
import { formatRupees } from '@/utils/formatters';

export interface PhoneMessagePreviewProps {
  customerName: string;
  amountRupees: number;
  cartSummary: string;
  paymentLinkUrl?: string;
  failureReason: string;
  category?: string;
  attemptNumber?: number;
  className?: string;
}

export const PhoneMessagePreview: React.FC<PhoneMessagePreviewProps> = ({
  customerName,
  amountRupees,
  cartSummary,
  paymentLinkUrl,
  failureReason,
  category,
  attemptNumber = 1,
  className,
}) => {
  // Generate authentic Hinglish-compliant copy matching app/llm/drafter.py
  const firstName = customerName.split(' ')[0];
  const formattedAmt = formatRupees(amountRupees);
  const rawUrl = paymentLinkUrl || 'http://localhost:8000/pay/test_sample_link';
  const linkUrl = rawUrl.startsWith('https://rzp.io/i/test_') || rawUrl.startsWith('https://rzp.io/i/mock_')
    ? `http://localhost:8000/pay/${rawUrl.split('/').pop()}`
    : rawUrl;

  let messageBody = '';
  if (category === 'technical_failure') {
    messageBody = `Hi ${firstName}, your payment of ${formattedAmt} for "${cartSummary}" failed due to a temporary bank issue (${failureReason.slice(0, 35)}...). You can complete it securely in 1 click here: ${linkUrl} (Link active for 24h). Reply STOP to opt out.`;
  } else if (category === 'authentication_drop') {
    messageBody = `Hi ${firstName}, looks like your OTP/auth timed out for "${cartSummary}" (${formattedAmt}). Retry seamlessly here without re-entering cart details: ${linkUrl}. Reply STOP to opt out.`;
  } else if (category === 'insufficient_funds') {
    messageBody = `Hi ${firstName}, your order for "${cartSummary}" (${formattedAmt}) is reserved. If you wish to retry with another card or UPI account, here is your link: ${linkUrl}. Reply STOP to opt out.`;
  } else {
    messageBody = `Hi ${firstName}, your cart for "${cartSummary}" (${formattedAmt}) is waiting for you. Complete your order here: ${linkUrl}. Reply STOP to opt out.`;
  }

  return (
    <div className={cn('flex flex-col items-center select-none', className)}>
      {/* Smartphone Outer Shell */}
      <div className="w-[280px] bg-ink rounded-[28px] p-2.5 shadow-2xl border-2 border-border-strong text-white font-sans">
        {/* Status Bar */}
        <div className="flex items-center justify-between px-3 pt-1 pb-2 text-[10px] text-ink-subtle">
          <span className="font-mono font-bold">10:15</span>
          <div className="w-16 h-3 bg-black rounded-full mx-auto" />
          <div className="flex items-center gap-1">
            <Signal className="w-2.5 h-2.5" />
            <Wifi className="w-2.5 h-2.5" />
            <Battery className="w-3 h-3" />
          </div>
        </div>

        {/* Messaging App Header */}
        <div className="bg-[#1F2C34] px-3 py-2 rounded-t-lg flex items-center gap-2 border-b border-[#2A3942]">
          <div className="w-7 h-7 rounded-full bg-accent flex items-center justify-center font-bold text-xs">
            R
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-xs font-semibold truncate text-white">Razorpay Recovery</div>
            <div className="text-[9px] text-[#8696A0] truncate">Verified Business Account</div>
          </div>
        </div>

        {/* Chat Screen Background */}
        <div className="bg-[#0B141A] p-3 rounded-b-lg min-h-[220px] flex flex-col justify-end space-y-2 text-xs">
          <div className="text-center text-[9px] text-[#8696A0] font-mono">
            TODAY ? ATTEMPT #{attemptNumber}
          </div>

          {/* Incoming Message Bubble */}
          <div className="bg-[#202C33] text-[#E9EDEF] p-2.5 rounded-lg rounded-tl-none border border-[#2A3942] space-y-1.5 shadow-sm">
            <p className="text-[11px] leading-relaxed font-normal">
              {messageBody.split(linkUrl)[0]}
              <a
                href={linkUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[#53BDEB] underline font-mono break-all font-medium inline-flex items-center gap-0.5 hover:text-white"
              >
                <span>{linkUrl}</span>
                <ExternalLink className="w-2.5 h-2.5 inline" />
              </a>
              {messageBody.split(linkUrl)[1]}
            </p>

            <div className="flex items-center justify-end gap-1 text-[9px] text-[#8696A0]">
              <span className="font-mono">10:15 AM</span>
              <CheckCheck className="w-3 h-3 text-[#53BDEB]" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
