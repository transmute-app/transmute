import { useState } from 'react'

function App() {
  const [count, setCount] = useState(0)

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center">
      <div className="bg-white rounded-lg shadow-xl p-8 max-w-md w-full">
        <h1 className="text-4xl font-bold text-center text-indigo-600 mb-6">
          Transmute
        </h1>
        <p className="text-gray-600 text-center mb-8">
          File conversion made simple
        </p>
        
        <div className="text-center">
          <button
            onClick={() => setCount((count) => count + 1)}
            className="bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-3 px-6 rounded-lg transition duration-200 shadow-md hover:shadow-lg"
          >
            Count: {count}
          </button>
        </div>
        
        <div className="mt-8 text-center text-sm text-gray-500">
          <p>Just a placeholder :)</p>
        </div>
      </div>
    </div>
  )
}

export default App
