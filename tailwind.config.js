// tailwind.config.js
module.exports = {
    content: [
      './templates/**/*.html',
      './static/js/**/*.js',
    ],
    theme: {
      extend: {
        colors: {
          'trust-blue':   '#1D4ED8',
          'alpine-oat':   '#F5F3E7',
          'butter-yellow':'#F9DC5C',
          'cherry-red':   '#E0245E',
          'slate-gray':   '#374151',
        },
      },
    },
    plugins: [],
  };
  