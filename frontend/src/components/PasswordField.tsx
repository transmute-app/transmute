import { useState, type ComponentPropsWithoutRef } from 'react'
import { FaEye, FaEyeSlash } from 'react-icons/fa6'
import { useTranslation } from 'react-i18next'

interface PasswordFieldProps extends Omit<ComponentPropsWithoutRef<'input'>, 'type'> {
  containerClassName?: string
  inputClassName?: string
  toggleButtonClassName?: string
}

function PasswordField({
  containerClassName = 'flex items-stretch gap-2',
  inputClassName,
  toggleButtonClassName,
  ...inputProps
}: PasswordFieldProps) {
  const [isVisible, setIsVisible] = useState(false)
  const { t } = useTranslation()
  const Icon = isVisible ? FaEyeSlash : FaEye
  const toggleLabel = isVisible ? t('password.hide') : t('password.show')

  return (
    <div className={containerClassName}>
      <input
        {...inputProps}
        type={isVisible ? 'text' : 'password'}
        className={['flex-1', inputClassName].filter(Boolean).join(' ')}
      />
      <button
        type="button"
        onClick={() => setIsVisible(visible => !visible)}
        className={toggleButtonClassName}
        aria-label={toggleLabel}
        aria-pressed={isVisible}
        title={toggleLabel}
      >
        <Icon className="text-base" />
      </button>
    </div>
  )
}

export default PasswordField